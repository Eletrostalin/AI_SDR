import os

import pandas as pd
import json
import logging


from classifier import client
from db.db import engine, SessionLocal
from db.dynamic_table_manager import create_dynamic_email_table
from db.email_table_db import process_table_operations
from promts.email_table_promt import generate_column_mapping_prompt, EMAIL_SEGMENT_COLUMNS
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def process_email_table(file_path: str, segment_table_name: str, bot, message) -> bool:
    """
    Обрабатывает загруженную таблицу, сопоставляет колонки и сохраняет данные в базу.
    """
    try:
        # Чтение таблицы
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file_path)
        else:
            await message.reply("Неподдерживаемый формат файла.")
            return False

        # Проверка на пустую таблицу
        if df.empty:
            await message.reply("Файл пуст или не содержит данных.")
            return False

        # Извлечение колонок
        user_columns = df.columns.tolist()
        logger.debug(f"Колонки пользователя: {user_columns}")

        # Генерация промпта и вызов модели для маппинга
        logger.debug("Отправка запроса для маппинга колонок...")
        prompt = generate_column_mapping_prompt(user_columns)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        mapping = json.loads(response.choices[0].message.content.strip())
        logger.debug(f"Полученный маппинг: {mapping}")

        # Проверка наличия маппинга
        if not mapping or not any(mapping.values()):
            await message.reply("Не удалось сопоставить загруженные данные с фиксированными колонками.")
            logger.warning("Маппинг колонок отсутствует или пуст.")
            return False

        # Переименование колонок в DataFrame
        df.rename(columns=mapping, inplace=True)
        logger.info(f"Переименованные колонки: {df.columns.tolist()}")
        logger.debug(f"Ожидаемые колонки: {EMAIL_SEGMENT_COLUMNS}")

        # Проверка на наличие ожидаемых колонок
        missing_columns = [col for col in EMAIL_SEGMENT_COLUMNS if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствующие колонки после маппинга: {missing_columns}")
            await message.reply(
                "Некоторые обязательные колонки отсутствуют после обработки. Пожалуйста, проверьте загруженный файл."
            )
            return False

        # Удаление лишних колонок
        df = df[[col for col in df.columns if col in EMAIL_SEGMENT_COLUMNS]]
        logger.info(f"Фильтрованные колонки: {df.columns.tolist()}")

        # Проверка данных после фильтрации
        if df.empty:
            logger.warning("Данные отсутствуют после фильтрации колонок.")
            await message.reply(
                "В обработанном файле отсутствуют данные после фильтрации. Проверьте, что в файле есть данные."
            )
            return False

        # Создание динамической таблицы, если она еще не существует
        logger.info(f"Попытка создания таблицы: {segment_table_name}")
        create_dynamic_email_table(engine, segment_table_name)
        logger.info(f"Таблица '{segment_table_name}' создана или уже существует.")

        chat_id = str(message.chat.id)
        file_name = os.path.basename(file_path)
        return process_table_operations(df, segment_table_name, chat_id, message, file_name)

    except Exception as e:
        logger.error(f"Ошибка при обработке файла {file_path}: {e}", exc_info=True)
        await message.reply(f"Произошла ошибка при обработке файла: {e}")
        return False

