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
CREDENTIALS_FILE = "/Users/nickstanchenkov/AI SDR/credentials.json"


IMAP_SERVER = "imap.example.com"  # Укажите ваш IMAP-сервер (например, imap.gmail.com)
IMAP_PORT = 993
EMAIL_ACCOUNT = "your-email@example.com"
EMAIL_PASSWORD = "your-email-password"