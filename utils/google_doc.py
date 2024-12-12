import os

import pandas as pd
from openpyxl.workbook import Workbook
from logger import logger



def create_excel_table(data, file_name=None):
    """
    Создает Excel-файл с таблицей данных.

    :param data: Двумерный список с данными для таблицы.
    :param file_name: Имя файла для сохранения (по умолчанию генерируется автоматически).
    :return: Путь к созданному файлу.
    """
    if file_name is None:
        file_name = "campaigns.xlsx"  # Значение по умолчанию

    # Создаем новую книгу и активный лист
    wb = Workbook()
    ws = wb.active

    # Заполняем таблицу данными
    for row in data:
        ws.append(row)

    # Сохраняем файл
    file_path = os.path.join(os.getcwd(), file_name)
    wb.save(file_path)
    return file_path


def create_excel_with_multiple_sheets(data: dict, file_name: str) -> str:
    """
    Создает Excel-файл с несколькими листами, используя openpyxl.

    :param data: Словарь, где ключ — имя листа, значение — данные для листа (в формате списков).
    :param file_name: Имя файла.
    :return: Путь к созданному файлу.
    """
    file_path = os.path.join(os.getcwd(), "uploads", file_name)  # Путь для сохранения файла
    os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Убедиться, что директория существует

    try:
        # Создаем новую книгу
        wb = Workbook()

        for i, (sheet_name, sheet_data) in enumerate(data.items()):
            # Если это первый лист, используем активный лист, иначе создаем новый
            if i == 0:
                ws = wb.active
                ws.title = sheet_name[:31]  # Ограничиваем длину названия до 31 символа
            else:
                ws = wb.create_sheet(title=sheet_name[:31])

            # Добавляем данные в лист
            for row in sheet_data:
                ws.append(row)

        # Сохраняем книгу
        wb.save(file_path)
        logger.info(f"Excel-файл с несколькими листами создан: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Ошибка при создании Excel-файла с несколькими листами: {e}", exc_info=True)
        raise