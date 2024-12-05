from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from db.db import SessionLocal
from db.models import User
from handlers.onboarding_handler import handle_company_name, handle_industry, handle_region, handle_contact_email, \
    handle_contact_phone, handle_additional_details, handle_confirmation
from utils.states import OnboardingState
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат.
    Проверяет, есть ли пользователь в базе. Если нет, запускает онбординг.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        user = event.new_chat_member.user
        chat_id = event.chat.id

        logger.debug(f"Новый пользователь {user.id} добавлен в чат {chat_id}. Проверка в базе данных.")

        db: Session = SessionLocal()
        try:
            # Проверяем наличие пользователя в базе
            existing_user = db.query(User).filter_by(telegram_id=str(user.id)).first()
            if not existing_user:
                logger.info(f"Пользователь {user.id} отсутствует в базе. Запуск онбординга.")
                # Устанавливаем состояние для начала онбординга
                await state.set_state(OnboardingState.waiting_for_company_name)
                await event.bot.send_message(
                    chat_id=chat_id,
                    text="👋 Добро пожаловать! Давайте начнем с базовой информации. Введите название вашей компании."
                )
            else:
                logger.info(f"Пользователь {user.id} уже существует в базе.")
        except Exception as e:
            logger.error(f"Ошибка при проверке пользователя в базе данных: {e}", exc_info=True)
        finally:
            db.close()


@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Обработчик всех сообщений в чате.
    Если пользователь проходит онбординг, маршрутизирует сообщения в соответствующие хендлеры.
    """
    current_state = await state.get_state()

    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {current_state}")

    if current_state is None:
        # Если состояние не установлено, бот пока не поддерживает сообщения
        await message.answer("Этот модуль находится в разработке.")
    elif current_state == OnboardingState.waiting_for_company_name.state:
        await handle_company_name(message, state)
    elif current_state == OnboardingState.waiting_for_industry.state:
        await handle_industry(message, state)
    elif current_state == OnboardingState.waiting_for_region.state:
        await handle_region(message, state)
    elif current_state == OnboardingState.waiting_for_contact_email.state:
        await handle_contact_email(message, state)
    elif current_state == OnboardingState.waiting_for_contact_phone.state:
        await handle_contact_phone(message, state)
    elif current_state == OnboardingState.waiting_for_additional_details.state:
        await handle_additional_details(message, state)
    elif current_state == OnboardingState.confirmation.state:
        await handle_confirmation(message, state)
    else:
        await message.answer("Неизвестное состояние. Пожалуйста, попробуйте снова.")