import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем токен для Telegram и URL базы данных из .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

SHEET_ID = "1YXv8CcjB_iOhDKAJZMkUV7BAmKE9x1kUrsN6cCWg2I8"
SHEET_NAME = "Черновики"

# 🔹 Подключаемся к Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_FILE = "credentials.json"


GOOGLE_SHEETS_POOL = {
    "https://docs.google.com/spreadsheets/d/1PBbkRgMBXhBtEC3Yl1TtMEFqZ26ly73t_jgikrLlyww/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1Jo3IViJ95uTlCvUZGKRIP1Bbaeq4PSLy_eB_BpyLex8/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1BxkNOt6tA8BmqXa5p0i-Aqix0iIg_0j-ocvkOxOKXOk/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1n7-JkaaQCXfBrlAgTjqy-TdBPmA8aAlU546rTidejTQ/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1mqCbx4EPWlpvmg0FvjwNGOGeOJIa4oCId57xGEJ_7Wk/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1GM4AHVGo3KyJvh7W_C0CrMbEccYQbg6G60GkfIfmWuI/edit?gid=0#gid=0": True,
    "https://docs.google.com/spreadsheets/d/1Mx83Nc2YodENWRPQaZHYYakW2iQ0oISvRuSNkhHYtP8/edit?gid=0#gid=0": True,
}