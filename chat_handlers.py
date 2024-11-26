from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from classifier import classify_message
from db.db import SessionLocal
from db.db_auth import create_or_get_company_and_user
from dispatcher import dispatch_classification  # Импорт диспетчера цепочек
from config import TARGET_CHAT_ID
import logging
from sqlalchemy.orm import Session

from handlers.campaign_handlers import process_campaign_information
from handlers.company_handlers import process_company_information, confirm_company_information
from utils.states import BaseState, AddCompanyState, AddCampaignState
from utils.utils import extract_text_from_url, process_message, extract_text_from_document

logger = logging.getLogger(__name__)
router = Router()


def setup_handlers(dp):
    dp.include_router(router)


@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Основной обработчик сообщений, маршрутизирующий их в зависимости от состояния пользователя.
    """
    # Проверяем ID чата
    if str(message.chat.id) != str(TARGET_CHAT_ID):
        logger.debug(f"Сообщение из неподдерживаемого чата: {message.chat.id}")
        return  # Игнорируем сообщение

    logger.debug(f"Получено сообщение: {message.text if message.text else 'нет текста'}")

    try:
        # Получаем текущее состояние пользователя
        current_state = await state.get_state()
        logger.debug(f"Текущее состояние пользователя: {current_state}")

        # Логика маршрутизации по состоянию
        if current_state is None or current_state == BaseState.default.state:
            # Пользователь в базовом состоянии, отправляем сообщение в классификатор
            logger.debug("Пользователь в базовом состоянии. Сообщение отправляется в классификатор.")
            try:
                classification = classify_message(message.text)
                logger.debug(f"Результат классификации: {classification}")
                await dispatch_classification(classification, message, state)
            except Exception as e:
                logger.error(f"Ошибка в классификаторе: {e}")
                await message.reply("Произошла ошибка при обработке сообщения. Попробуйте снова.")
        elif current_state == AddCompanyState.waiting_for_information.state:
            # Пользователь добавляет информацию о компании
            logger.debug("Пользователь в состоянии AddCompanyState:waiting_for_information. Обрабатываем сообщение.")
            await process_company_information(message, state, bot=message.bot)
        elif current_state == AddCompanyState.waiting_for_confirmation.state:
            # Пользователь подтверждает информацию о компании
            logger.debug("Пользователь в состоянии AddCompanyState:waiting_for_confirmation. Обрабатываем сообщение.")
            await confirm_company_information(message, state)
        elif current_state == AddCampaignState.waiting_for_campaign_information.state:
            # Пользователь добавляет информацию о кампании
            logger.debug("Пользователь в состоянии AddCampaignState:waiting_for_campaign_information. Обрабатываем сообщение.")
            await process_campaign_information(message, state)
        else:
            # Если состояние неизвестно, уведомляем пользователя
            logger.warning(f"Неизвестное состояние: {current_state}")
            await message.reply("Произошла ошибка. Пожалуйста, попробуйте снова.")

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await message.reply("Произошла ошибка при обработке вашего сообщения. Попробуйте снова.")



@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated):
    """
    Обработчик добавления нового пользователя в чат.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        user_name = event.new_chat_member.user.full_name
        chat_id = event.chat.id
        telegram_id = event.new_chat_member.user.id

        # Логирование добавления нового пользователя
        logger.debug(f"Пользователь {user_name} добавлен в чат {chat_id}. Проверяем и добавляем в базу данных.")

        # Добавление пользователя и компании в базу данных
        db: Session = SessionLocal()
        try:
            user = create_or_get_company_and_user(db, telegram_id, chat_id)
            logger.info(f"Пользователь {user_name} с ID {telegram_id} добавлен в базу данных.")
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя в базу данных: {e}")
        finally:
            db.close()

        # Отправка приветственного сообщения
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"Добро пожаловать, {user_name}! 👋\nРады видеть вас в нашем чате."
        )