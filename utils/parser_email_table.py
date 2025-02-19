import os
import pandas as pd
import json
import logging
from classifier import client
from db.db import engine, SessionLocal
from db.dynamic_table_manager import create_dynamic_email_table
from db.email_table_db import process_table_operations
from db.segmentation import EMAIL_SEGMENT_COLUMNS
from promts.email_table_promt import generate_column_mapping_prompt
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

logger = logging.getLogger(__name__)

async def process_email_table(file_path: str, segment_table_name: str, bot, message) -> bool:
    """
    Обрабатывает загруженную таблицу Excel, выполняет маппинг колонок, очищает данные и сохраняет их в базу.
    """
    try:
        # Читаем только Excel-файлы
        df = pd.read_excel(file_path)

        # Проверка на пустую таблицу
        if df.empty:
            await message.reply("Файл пуст или не содержит данных.")
            return False

        # === Очистка данных ===
        df.dropna(how="all", inplace=True)  # Удаляем полностью пустые строки
        df.fillna("", inplace=True)  # Заменяем NaN на пустые строки
        df = df[~df.apply(lambda row: row.astype(str).str.strip().eq("").all(), axis=1)]  # Удаляем строки, где все колонки пустые

        if df.empty:
            logger.warning("После очистки не осталось данных для обработки.")
            await message.reply("Файл не содержит значимых данных после очистки. Проверьте его содержимое.")
            return False

        # Очищаем заголовки от пробелов и случайных символов
        df.columns = df.columns.str.strip()

        # Проверка количества колонок
        user_columns = df.columns.tolist()
        logger.debug(f"Колонки пользователя: {user_columns}")

        # === Генерация промпта и маппинг колонок ===
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

        # === Проверка e-mail перед записью в базу ===
        email_column = next((col for col in df.columns if "email" in col.lower()), None)

        if email_column:
            # Фильтруем записи без e-mail
            total_rows = len(df)
            df = df[df[email_column].str.strip() != ""]  # Удаляем записи без e-mail
            removed_rows = total_rows - len(df)  # Считаем, сколько строк убрали

            if removed_rows > 0:
                await message.reply(
                    f"В загружаемой таблице {removed_rows} записей **не будут добавлены**, так как e-mail отсутствует.")

            # Оставляем только первый e-mail в ячейке (если их несколько)
            df[email_column] = df[email_column].str.extract(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

            logger.info("Обработаны e-mail'ы. Оставлены только первые адреса в ячейке.")
        else:
            await message.reply(
                "Ошибка: В загружаемой таблице не найдена колонка e-mail. Проверьте, что e-mail присутствует в файле.")
            return False

        # Проверка на наличие ожидаемых колонок
        missing_columns = [col for col in EMAIL_SEGMENT_COLUMNS if col not in df.columns]
        if missing_columns:
            logger.warning(f"Отсутствующие колонки после маппинга: {missing_columns}")
            await message.reply("Некоторые обязательные колонки отсутствуют после обработки. Проверьте загруженный файл.")
            return False

        # Удаление лишних колонок
        df = df[[col for col in df.columns if col in EMAIL_SEGMENT_COLUMNS]]
        logger.info(f"Фильтрованные колонки: {df.columns.tolist()}")

        # Проверка данных после фильтрации
        if df.empty:
            logger.warning("Данные отсутствуют после фильтрации колонок.")
            await message.reply("В обработанном файле отсутствуют данные после фильтрации. Проверьте, что в файле есть данные.")
            return False

        # === Проверка и создание таблицы ===
        logger.info(f"🔍 Проверяем наличие таблицы '{segment_table_name}'...")
        inspector = inspect(engine)
        if not inspector.has_table(segment_table_name):
            create_dynamic_email_table(engine, segment_table_name)
            logger.info(f"✅ Таблица '{segment_table_name}' создана.")
        else:
            logger.info(f"✅ Таблица '{segment_table_name}' уже существует.")

        # === Сохранение данных ===
        chat_id = str(message.chat.id)
        file_name = os.path.basename(file_path)
        return process_table_operations(df, segment_table_name, chat_id, message, file_name)

    except Exception as e:
        logger.error(f"Ошибка при обработке файла {file_path}: {e}", exc_info=True)
        await message.reply(f"Произошла ошибка при обработке файла: {e}")
        return False


def count_table_rows(table_name: str) -> int:
    """
    Подсчитывает количество записей в указанной таблице.
    """
    db: Session = SessionLocal()
    try:
        query = text(f"SELECT COUNT(*) FROM {table_name}")
        result = db.execute(query).scalar()
        return result or 0
    except Exception as e:
        print(f"Ошибка при подсчёте строк в таблице {table_name}: {e}")
        return 0
    finally:
        db.close()