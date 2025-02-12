import asyncio
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from logger import logger
from handlers.campaign_handlers.campaign_delete_handler import (
    handle_delete_campaign_request,
    handle_campaign_deletion_callback,  # Обработчик инлайн-кнопок для удаления кампаний
)
from chat_handlers import router as chat_router
from admin.admin_commands import router as home_router
from handlers.company_handlers.company_handlers import router as company_router
from handlers.onboarding_handler import router as onboarding_router
from handlers.template_handlers.template_handler import router as template_router
from handlers.campaign_handlers.campaign_handlers import router as campaign_router
from handlers.draft_handlers.draft_handler import router as draft_router
from bot import bot
from config import TARGET_CHAT_ID


async def main():
    # Логирование начала работы бота
    logger.info("Запуск бота...")

    # Применение миграций перед запуском
    logger.info("Применение миграций...")
    #apply_migrations()
    logger.info("Миграции успешно применены.")

    dp = Dispatcher(storage=MemoryStorage())

    # Настраиваем маршрутизаторы
    setup_routers(dp)
    logger.info("Маршрутизаторы настроены.")
    logger.info(f"Целевой ID чата: {TARGET_CHAT_ID}")

    # Запуск поллинга
    await dp.start_polling(bot)
    logger.info("Бот начал опрос сообщений.")


def setup_routers(dp: Dispatcher):
    """
    Настраивает маршрутизаторы, подключая обработчики для чата с пользователями
    и для команд администратора.
    """
    dp.include_router(home_router)  # Регистрация команды /home
    dp.include_router(chat_router)
    dp.include_router(company_router)
    dp.include_router(campaign_router)
    dp.include_router(template_router)
    dp.include_router(draft_router)

    # Регистрация маршрутизатора для онбординга

    dp.include_router(onboarding_router)

    # Регистрация команды для удаления кампании
    dp.message.register(
        handle_delete_campaign_request,
        Command("delete_campaign")  # Используем Command фильтр
    )

    # Регистрация обработчика инлайн-кнопок для удаления кампаний
    dp.callback_query.register(
        handle_campaign_deletion_callback,
        lambda callback: callback.data.startswith("delete_campaign:")
    )


if __name__ == "__main__":
    asyncio.run(main())