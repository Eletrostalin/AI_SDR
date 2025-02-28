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

    # Добавляем логирование перед отправкой в OpenAI
    logger.debug(
        f"📤 Данные, отправляемые в модель: {json.dumps({'messages': [{'role': 'user', 'content': prompt}]}, indent=2, ensure_ascii=False)}")

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )

    mapping = json.loads(response.choices[0].message.content.strip())

    logger.debug(f"🔄 Полученный маппинг: {mapping}")

    # Проверяем, содержит ли email-колонка "email" в названии
    email_column = mapping.get("email", None)
    if email_column and not any(keyword in email_column.lower() for keyword in ["email", "почта", "mail"]):
        logger.warning(f"⚠️ Колонка '{email_column}' была ошибочно назначена как email!")
        return None  # Прерываем маппинг

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
        return df, None, 0, [], []  # Нет email-колонки

    df[email_column] = df[email_column].astype(str).str.strip()

    multi_email_rows = []
    problematic_values = []

    for index, value in df[email_column].items():
        count, emails = count_emails_in_cell(value)
        if count > 1:
            multi_email_rows.append(index + 1)  # +1, чтобы соответствовало Excel
            problematic_values.append(", ".join(emails))

    return df, email_column, len(multi_email_rows), multi_email_rows, problematic_values


async def save_cleaned_data(df: pd.DataFrame, segment_table_name: str, message):
    """Сохраняет очищенные данные в БД."""
    missing_columns = [col for col in EMAIL_SEGMENT_COLUMNS if col not in df.columns]

    if missing_columns:
        await message.reply("⚠️ Некоторые обязательные колонки отсутствуют. Проверьте загруженный файл.")
        return False

    df = df[[col for col in df.columns if col in EMAIL_SEGMENT_COLUMNS]]
    if df.empty:
        await message.reply("❌ В обработанном файле отсутствуют данные после фильтрации.")
        return False

    if not inspect(engine).has_table(segment_table_name):
        create_dynamic_email_table(engine, segment_table_name)
        logger.info(f"✅ Таблица '{segment_table_name}' создана.")

    chat_id = str(message.chat.id)
    file_name = "email_data.xlsx"
    process_table_operations(df, segment_table_name, chat_id, message, file_name)
    await message.reply(f"✅ Данные успешно загружены! 📊 Итоговое количество записей: **{len(df)}**.")
    return True