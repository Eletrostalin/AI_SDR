import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from openai import OpenAI

from bot import setup_routers
from config import TELEGRAM_TOKEN, TARGET_CHAT_ID

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    # Логирование начала работы бота
    logger.info("Запуск бота...")



    # Создаем бота и диспетчер
    bot = Bot(token=TELEGRAM_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Настраиваем маршрутизаторы
    setup_routers(dp)
    logger.info("Маршрутизаторы настроены.")
    logger.info(f"Целевой ID чата: {TARGET_CHAT_ID}")

    # Запуск поллинга
    await dp.start_polling(bot)
    logger.info("Бот начал опрос сообщений.")


if __name__ == "__main__":
    asyncio.run(main())