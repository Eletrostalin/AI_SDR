
import os
from datetime import datetime

import pandas as pd
from openpyxl.workbook import Workbook
from logger import logger


def create_excel_table(data: list, file_name: str = "content_plans.xlsx") -> str:
    """
    Создает Excel-файл с переданными данными.

    :param data: Двумерный список данных для таблицы.
    :param file_name: Имя создаваемого файла.
    :return: Путь к созданному файлу.
    """
    # Создаем DataFrame из списка данных
    df = pd.DataFrame(data[1:], columns=data[0])  # Первая строка — заголовки

    # Генерируем путь к файлу
    directory = "generated_reports"
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name}")

    # Сохраняем в Excel
    df.to_excel(file_path, index=False)

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