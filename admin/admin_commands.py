from aiogram.exceptions import TelegramMigrateToChat
from aiogram.types import Message
from sqlalchemy.orm import Session
from aiogram.filters import Command
from logger import logger

from admin.ThreadManager import create_new_thread
from chat_handlers import router
from db.db import SessionLocal
from db.db_thread import save_thread_to_db



@router.message(Command("init"))
async def initialize_topics(message: Message):
    """
    Команда /init: Создание тем в чате.
    """
    chat_id = message.chat.id
    bot = message.bot

    try:
        # Получаем информацию о чате
        chat = await bot.get_chat(chat_id)

        # Проверяем, поддерживает ли чат темы
        if not chat.is_forum:
            await message.answer("Этот чат не поддерживает темы. Включите их в настройках чата.")
            return

        # Проверяем права бота
        admins = await bot.get_chat_administrators(chat_id)
        bot_admin = next((admin for admin in admins if admin.user.id == bot.id), None)
        if not bot_admin or not bot_admin.can_manage_chat:
            await message.answer("У бота недостаточно прав для управления темами.")
            return

        db: Session = SessionLocal()
        try:
            created_threads = []

            # Создание темы "Notification"
            notification_topic_id = await create_new_thread(bot, chat_id, "Notification")
            if notification_topic_id:
                save_thread_to_db(db, chat_id, notification_topic_id, "Notification")
                created_threads.append("Notification")

            logger.info(f"Темы {created_threads} успешно созданы в чате {chat_id}.")
            await message.answer(f"Темы {', '.join(created_threads)} успешно созданы.")
        except Exception as e:
            logger.error(f"Ошибка при создании тем в чате {chat_id}: {e}", exc_info=True)
            await message.answer("Произошла ошибка при создании тем. Проверьте логи бота.")
        finally:
            db.close()

    except TelegramMigrateToChat as migrate_error:
        new_chat_id = migrate_error.migrate_to_chat_id
        logger.warning(f"Чат обновлён до супергруппы. Новый ID: {new_chat_id}")
        await message.answer(f"Чат обновлён до супергруппы. Новый ID: {new_chat_id}. Повторите команду.")
    except Exception as e:
        logger.error(f"Ошибка обработки команды /init в чате {chat_id}: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке команды. Проверьте логи бота.")


from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

# Инициализируем маршрутизатор
router = Router()

@router.message(Command("home"))
async def home_command_handler(message: types.Message, state: FSMContext):
    """
    Обработчик команды /home.
    Сбрасывает состояние и отправляет приветственное сообщение.
    """
    # Сброс состояния
    await state.clear()

    # Отправляем приветственное сообщение
    await message.answer(
        "Состояние сброшено"
    )