import gspread
from google.oauth2.service_account import Credentials
from logger import logger
import os
from datetime import datetime

import pandas as pd
from openpyxl.workbook import Workbook
from logger import logger


# 🔹 Подключаемся к Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"  # Загрузи свой JSON-файл с ключами


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


def connect_to_google_sheets(sheet_id: str, sheet_name: str):
    """Создает подключение к Google Sheets."""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet(sheet_name)
    return sheet

def append_drafts_to_sheet(sheet_id: str, sheet_name: str, drafts):
    """
    Добавляет список черновиков в Google Таблицу.

    :param sheet_id: ID Google Таблицы.
    :param sheet_name: Имя листа.
    :param drafts: Список черновиков (dict).
    """
    try:
        sheet = connect_to_google_sheets(sheet_id, sheet_name)

        rows = [[
            draft["lead_id"],   # ✅ Соответствует "id"
            draft["email"],     # ✅ Соответствует "e-mail получателя"
            draft["subject"],   # ✅ Соответствует "Тема"
            draft["text"]       # ✅ Соответствует "текст письма"
        ] for draft in drafts]

        sheet.append_rows(rows, value_input_option="RAW")
        logger.info(f"✅ Добавлено {len(rows)} черновиков в Google Таблицу.")
    except Exception as e:
        logger.error(f"❌ Ошибка при записи в Google Sheets: {e}", exc_info=True)