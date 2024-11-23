from chat_handlers import router as chat_router
from handlers.company_handlers import router as company_router
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv


# Загружаем переменные окружения
load_dotenv()

# Инициализация асинхронного клиента

def setup_routers(dp):
    """
    Настраивает маршрутизаторы, подключая обработчики для чата с пользователями
    и для команд администратора.
    """
    dp.include_router(chat_router)
    dp.include_router(company_router)