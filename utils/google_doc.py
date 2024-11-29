from googleapiclient.discovery import build
from google.oauth2 import service_account
from config import SERVICE_ACCOUNT_FILE, SCOPES


def create_google_sheets_table(data, title="Таблица кампаний"):
    """
    Создает Google Sheets документ с таблицей и предоставляет права доступа на чтение всем, у кого есть ссылка.

    :param data: Двумерный список с данными для таблицы.
    :param title: Заголовок документа.
    :return: URL созданного Google Sheets.
    """
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    # Инициализируем сервисы Google Sheets и Drive
    sheets_service = build("sheets", "v4", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)

    # Создаем пустой Google Sheets документ
    sheet_body = {"properties": {"title": title}}
    sheet = sheets_service.spreadsheets().create(body=sheet_body).execute()
    sheet_id = sheet["spreadsheetId"]

    try:
        # Заполняем Google Sheets данными
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",  # Начальная ячейка для вставки данных
            valueInputOption="RAW",
            body={"values": data}
        ).execute()

        # Устанавливаем права доступа на просмотр для всех
        drive_service.permissions().create(
            fileId=sheet_id,
            body={"type": "anyone", "role": "reader"},
            fields="id"
        ).execute()

        # Формируем ссылку на Google Sheets
        google_sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        return google_sheet_url
    except Exception as e:
        print(f"Ошибка при создании Google Sheets таблицы: {e}")
        raise e