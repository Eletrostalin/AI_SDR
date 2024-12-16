from aiogram import Bot
from config import TELEGRAM_TOKEN
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()



# Экземпляр бота
bot = Bot(token=TELEGRAM_TOKEN)

