import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем токен для Telegram и URL базы данных из .env
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")