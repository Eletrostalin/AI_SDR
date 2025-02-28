import pandas as pd
import pdfplumber
from docx import Document
import mimetypes
from aiogram.types import File

import logging
from classifier import client  # Здесь используется клиент для работы с моделью

logger = logging.getLogger(__name__)


def send_to_model(prompt: str) -> dict:
    """
    Отправляет запрос в модель OpenAI и возвращает результат.

    :param prompt: Текстовый запрос для модели.
    :return: Результат работы модели в виде словаря.
    """
    try:
        logger.debug(f"Отправляем запрос в модель с prompt: {prompt}")

        # Отправляем запрос
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Логируем полный ответ
        logger.debug(f"Полный ответ от модели: {response}")

        # Проверяем и извлекаем текст ответа
        if response.choices and len(response.choices) > 0:
            result = response.choices[0].message.content.strip()
            logger.debug(f"Извлеченный результат: {result}")
            return result
        else:
            raise ValueError("Ответ модели не содержит 'choices' или они пусты.")

    except Exception as e:
        logger.error(f"Ошибка при обращении к модели: {e}")
        raise


async def find_header_row(df: pd.DataFrame) -> int:
    """
    Определяет строку заголовков, выбирая первую строку, где:
    - Нет NaN
    - Все значения являются строками (без чисел и спецсимволов)
    """
    for i in range(len(df)):
        row = df.iloc[i]

        # Проверяем, есть ли NaN
        if row.isna().any():
            continue  # Пропускаем строки с пустыми значениями

        # Проверяем, что все ячейки содержат только текст (и не являются числами)
        if all(isinstance(cell, str) and cell.isprintable() for cell in row):
            return i  # Это заголовки!

    return 0  # Если не нашли, используем первую строку по умолчанию


# Определение типа сообщения
async def process_message(message, bot):
    """
    Определяет тип сообщения: текст, файл или ссылка.
    """
    if message.text:
        if "http" in message.text:  # Если это ссылка
            return {"type": "link", "content": message.text}
        else:
            return {"type": "text", "content": message.text}
    elif message.document:
        mime_type, _ = mimetypes.guess_type(message.document.file_name)

        # Получаем объект File
        file: File = await bot.get_file(message.document.file_id)

        # Указываем путь для временного сохранения файла
        file_path = f"/tmp/{message.document.file_name}"

        # Скачиваем файл в указанный путь
        await bot.download(file, destination=file_path)

        return {
            "type": "file",
            "mime_type": mime_type,
            "file_path": file_path,
            "file_name": message.document.file_name,
        }
    else:
        return {"type": "unknown", "content": None}