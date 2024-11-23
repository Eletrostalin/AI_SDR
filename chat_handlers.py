from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ChatMemberUpdated
from sqlalchemy.orm import Session

from classifier import classify_message
from config import TARGET_CHAT_ID
from db.models import User, Company
from db.db_auth import create_user_and_company
from dispatcher import dispatch_classification
from utils.states import BaseState
from db.db import SessionLocal  # Подключение к базе данных

import logging

logger = logging.getLogger(__name__)
router = Router()

storage = MemoryStorage()

def setup_handlers(dp):
    dp.include_router(router)


@router.message(StateFilter(None))  # Обрабатываем сообщения без установленного состояния
async def set_default_state(message: Message, state: FSMContext):
    """
    Устанавливает базовое состояние для сообщений без установленного состояния.
    """
    await state.set_state(BaseState.default)
    logger.debug(f"Установлено базовое состояние для пользователя {message.from_user.id}")
    await handle_message(message, state)  # Передаем сообщение в основной обработчик


@router.message(StateFilter(BaseState.default))  # Обрабатываем сообщения в базовом состоянии
async def handle_message(message: Message, state: FSMContext):
    """
    Обрабатывает входящие сообщения от пользователей в базовом состоянии.
    """
    # Преобразуем ID чата в строку
    chat_id_str = str(message.chat.id)

    if chat_id_str != str(TARGET_CHAT_ID):
        logger.debug(f"Сообщение из неподдерживаемого чата: {message.chat.id}")
        return  # Игнорируем сообщение

    # Проверяем, есть ли текстовое сообщение
    if not message.text:
        logger.debug("Получено сообщение без текста. Игнорируем.")
        return

    logger.debug(f"Получено сообщение: {message.text}")

    # Передача сообщения на классификацию
    classification = await classify_message(message.text)
    logger.debug(f"Результат классификации: {classification}")

    # Передача результата классификации в диспетчер
    await dispatch_classification(classification, message, state)
    logger.debug(f"Классификация обработана: {classification}")


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated):
    """
    Приветствует нового пользователя, добавленного в чат, и создаёт запись в базе данных.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        user_name = event.new_chat_member.user.full_name
        telegram_id = str(event.new_chat_member.user.id)  # Преобразуем в строку
        chat_id = str(event.chat.id)  # Преобразуем в строку

        # Открываем сессию для работы с базой данных
        db = SessionLocal()
        try:
            # Создаём пользователя и компанию (если они ещё не существуют)
            existing_user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not existing_user:
                create_user_and_company(db, telegram_id=telegram_id, chat_id=chat_id)
                logger.debug(f"Создан пользователь {user_name} и компания для чата {chat_id}.")
            else:
                logger.debug(f"Пользователь {user_name} уже существует в базе.")

            # Устанавливаем базовое состояние через FSMContext
            state_key = f"{telegram_id}:{chat_id}"  # Убедитесь, что это строка
            state = FSMContext(storage=storage, key=state_key)
            await state.set_state(BaseState.default)
            logger.debug(f"Установлено базовое состояние для пользователя {user_name}.")

        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя: {str(e)}")
        finally:
            db.close()

        # Отправляем приветственное сообщение
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"Добро пожаловать, {user_name}! 👋\nРады видеть вас в нашем чате."
        )