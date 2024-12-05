from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated, ContentType
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session

from classifier import classify_message
from db.db import SessionLocal
from db.db_auth import create_or_get_company_and_user
from db.models import Company
from dispatcher import dispatch_classification
from handlers.onboarding_handler import handle_company_name, handle_industry, handle_region, handle_contact_email, \
    handle_contact_phone, handle_additional_details, handle_confirmation
from utils.states import OnboardingState, BaseState
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        telegram_user = event.new_chat_member.user
        chat_id = event.chat.id

        logger.debug(f"Новый пользователь {telegram_user.full_name} добавлен в чат {chat_id}. Проверка в базе данных.")
        db: Session = SessionLocal()
        try:
            # Проверяем существование компании до вызова create_or_get_company_and_user
            existing_company = db.query(Company).filter_by(chat_id=str(chat_id)).first()
            print(existing_company)

            # Создаём или получаем компанию и пользователя
            user = create_or_get_company_and_user(db, telegram_user, chat_id)

            if not existing_company:
                # Если компания не существовала, это первый пользователь компании
                await state.update_data(company_id=user.company_id)  # Сохраняем company_id в состояние
                await state.set_state(OnboardingState.waiting_for_company_name)
                await event.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "👋 Добро пожаловать! Давайте начнем с базовой информации.\n"
                        "Введите название вашей компании."
                    )
                )
            else:
                # Приветственное сообщение для последующих пользователей
                await event.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                        "Вы добавлены к текущей компании. Напишите 'Помощь', чтобы узнать, что я могу делать."
                    )
                )
        except Exception as e:
            logger.error(f"Ошибка обработки нового пользователя: {e}", exc_info=True)
        finally:
            db.close()

@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Обработчик всех сообщений в чате.
    Если пользователь добавлен в чат, запускается онбординг.
    Если состояние отсутствует, устанавливается базовое состояние, и сообщение направляется в классификатор.
    """
    current_state = await state.get_state()
    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {current_state}")

    # Проверяем системные сообщения
    if message.content_type in {ContentType.NEW_CHAT_MEMBERS, ContentType.LEFT_CHAT_MEMBER}:
        if message.content_type == ContentType.NEW_CHAT_MEMBERS:
            # Обрабатываем добавление нового пользователя
            for new_member in message.new_chat_members:
                event = ChatMemberUpdated(
                    chat=message.chat,
                    from_user=message.from_user,
                    new_chat_member=new_member,
                    old_chat_member=message.from_user,
                )
                logger.debug(f"Обрабатываем добавление нового пользователя: {new_member.full_name}")
                await greet_new_user(event, state)
        logger.debug("Системное сообщение обработано. Пропускаем обработку.")
        return

    # Если состояние не установлено, устанавливаем базовое состояние
    if current_state is None:
        logger.debug("Состояние отсутствует. Устанавливаем базовое состояние и классифицируем сообщение.")
        await state.set_state(BaseState.default.state)  # Устанавливаем базовое состояние
        try:
            classification = classify_message(message.text)  # Классификация сообщения
            logger.debug(f"Результат классификации: {classification}")
            await dispatch_classification(classification, message, state)  # Передача в диспетчер
        except Exception as e:
            logger.error(f"Ошибка в процессе классификации: {e}", exc_info=True)
            await message.reply("Произошла ошибка при обработке вашего сообщения. Попробуйте снова.")
        return

    # Обработка состояний онбординга
    if current_state == OnboardingState.waiting_for_company_name.state:
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