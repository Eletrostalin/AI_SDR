import pandas as pd
import re
import json
import logging
from classifier import client
from db.db import engine
from db.dynamic_table_manager import create_dynamic_email_table
from db.email_table_db import process_table_operations
from db.segmentation import EMAIL_SEGMENT_COLUMNS
from sqlalchemy import inspect
from aiogram.fsm.context import FSMContext
from promts.email_table_promt import generate_column_mapping_prompt

logger = logging.getLogger(__name__)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """ Очищает DataFrame от пустых строк и значений. """
    df.dropna(how="all", inplace=True)
    df.fillna("", inplace=True)
    df = df[~df.apply(lambda row: row.astype(str).str.strip().eq("").all(), axis=1)]
    df.columns = df.columns.str.strip()
    return df


async def map_columns(user_columns: list) -> dict:
    """ Отправляет запрос на маппинг колонок через ИИ и логирует данные перед отправкой. """
    logger.debug("🔄 Отправка запроса для маппинга колонок...")

    prompt = generate_column_mapping_prompt(user_columns)

    logger.debug(f"📤 Данные, отправляемые в модель: {json.dumps({'messages': [{'role': 'user', 'content': prompt}]}, indent=2, ensure_ascii=False)}")

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    logger.debug(f"📩 Полный ответ от OpenAI перед обработкой: {response}")

    # Получаем сырое содержимое ответа
    raw_response = response.choices[0].message.content.strip() if response.choices else ""

    # Если ответ пустой — ошибка
    if not raw_response:
        logger.error("❌ Ошибка: пустой ответ от OpenAI API. Проверь параметры запроса.")
        return {}

    # Проверяем, есть ли Markdown-обёртка, и удаляем её только если она есть
    if raw_response.startswith("```json") and raw_response.endswith("```"):
        cleaned_response = re.sub(r"^```json\s*|\s*```$", "", raw_response).strip()
    else:
        cleaned_response = raw_response  # Оставляем без изменений, если обёртки нет

    try:
        mapping = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка декодирования JSON: {e}. Оригинальный ответ: {raw_response}")
        return {}

    logger.debug(f"🔄 Полученный маппинг: {mapping}")

    return mapping if mapping and any(mapping.values()) else None


def count_emails_in_cell(cell):
    """ Подсчет количества email в ячейке, используя '@' и разделение по пробелам, запятым и точкам с запятой. """
    if pd.isna(cell) or not isinstance(cell, str):
        return 0, []  # Если пусто или не строка

    # Очищаем от лишних пробелов, переносов строк
    cell = re.sub(r"\s+", " ", cell.strip())

    # Разделяем строку по пробелам, запятым и точкам с запятой
    parts = re.split(r"[ ,;]", cell)

    # Фильтруем: оставляем только email-адреса (должны содержать '@')
    emails = [part for part in parts if "@" in part]

    return len(emails), emails


def clean_and_validate_emails(df: pd.DataFrame) -> tuple:
    """Очищает e-mail колонки, подсчитывает записи с несколькими email и возвращает номера строк и значения."""

    email_column = next((col for col in df.columns if "email" in col.lower()), None)

    if not email_column:
        logger.warning("⚠️ Внимание: В загруженной таблице не найдено колонок, содержащих 'email'.")
        return df, None, 0, [], []  # Нет email-колонки

    df[email_column] = df[email_column].astype(str).str.strip()

    multi_email_rows = []
    problematic_values = []

    logger.debug(f"📩 Начинаем проверку email-колонки: {email_column}")

    for index, value in df[email_column].items():
        logger.debug(f"🔍 Обрабатываем строку {index + 1}: '{value}'")

        count, emails = count_emails_in_cell(value)

        if count > 1:
            logger.info(f"📌 В строке {index + 1} найдено {count} email: {emails}")
            multi_email_rows.append(index + 1)  # +1, чтобы соответствовало Excel
            problematic_values.append(", ".join(emails))

    logger.info(f"✅ Найдено {len(multi_email_rows)} строк с несколькими email.")

    return df, email_column, len(multi_email_rows), multi_email_rows, problematic_values


async def save_cleaned_data(df: pd.DataFrame, segment_table_name: str, message, state: FSMContext):
    """Сохраняет очищенные данные в БД, оставляя только необходимые колонки."""

    # Извлекаем `file_name` из состояния FSM
    state_data = await state.get_data()
    file_name = state_data.get("file_name")

    if not file_name:
        await message.reply("⚠️ Ошибка: не удалось определить имя файла.")
        return False

    logger.debug(f"📌 Используется file_name: {file_name}")

    # **Добавляем file_name в DataFrame**
    df["file_name"] = file_name  # Добавляем колонку с названием файла

    # **Обновляем список обязательных колонок**
    REQUIRED_COLUMNS = EMAIL_SEGMENT_COLUMNS + ["file_name"]
    MANDATORY_COLUMNS = ["email", "file_name"]  # Обязательные колонки

    logger.debug(f"📌 REQUIRED_COLUMNS: {REQUIRED_COLUMNS}")
    logger.debug(f"📌 Фактические колонки в DataFrame перед фильтрацией: {df.columns.tolist()}")

    # **Оставляем только нужные колонки**
    df = df[[col for col in df.columns if col in REQUIRED_COLUMNS]]

    logger.debug(f"📌 Итоговые колонки после фильтрации: {df.columns.tolist()}")

    # **Добавляем отсутствующие колонки из REQUIRED_COLUMNS и заполняем их None**
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None  # Заполняем None, так как пользователь не загрузил эти данные

    logger.debug(f"📌 Итоговые колонки после добавления недостающих: {df.columns.tolist()}")

    # Проверяем, есть ли обязательные колонки
    missing_mandatory = [col for col in MANDATORY_COLUMNS if col not in df.columns]
    if missing_mandatory:
        await message.reply(f"⚠️ Отсутствуют обязательные колонки: {', '.join(missing_mandatory)}. Проверьте загруженный файл.")
        return False

    # Проверяем, существует ли таблица
    if not inspect(engine).has_table(segment_table_name):
        create_dynamic_email_table(engine, segment_table_name)
        logger.info(f"✅ Таблица '{segment_table_name}' создана.")

    # Получаем chat_id
    chat_id = str(message.chat.id)

    # Передаём `file_name` в `process_table_operations`
    result = process_table_operations(df, file_name, chat_id, message, segment_table_name)

    if result:
        await message.reply(f"✅ База email загружена. Доступно записей: {len(df)}.")
    else:
        await message.reply(f"❌ Ошибка при обработке данных из {file_name}.")

    return result