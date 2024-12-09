import os
from openpyxl.workbook import Workbook


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