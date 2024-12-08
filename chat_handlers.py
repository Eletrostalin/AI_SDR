from aiogram import Router, Bot
from aiogram.exceptions import TelegramMigrateToChat
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, ChatMemberUpdated, ContentType
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from aiogram.filters import Command

from admin.ThreadManager import save_thread_to_db, create_new_thread
from classifier import classify_message
from db.db import SessionLocal
from db.db_auth import create_or_get_company_and_user
from db.models import Company
from dispatcher import dispatch_classification
from handlers.company_handlers import process_edit_company_information, confirm_edit_company_information
from handlers.onboarding_handler import handle_company_name, handle_industry, handle_region, handle_contact_email, \
    handle_contact_phone, handle_additional_details, handle_confirmation
from utils.states import OnboardingState, BaseState, EditCompanyState
import logging

logger = logging.getLogger(__name__)
router = Router()



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


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        telegram_user = event.new_chat_member.user
        chat_id = event.chat.id
        bot_id = event.bot.id  # Получаем ID бота

        logger.debug(f"Новый пользователь {telegram_user.full_name} добавлен в чат {chat_id}. Проверка в базе данных.")
        db: Session = SessionLocal()
        try:
            # Проверяем существование компании
            existing_company = db.query(Company).filter_by(chat_id=str(chat_id)).first()

            # Создаём или получаем компанию и пользователя
            user = create_or_get_company_and_user(db, telegram_user, chat_id)

            if not existing_company:
                # Если компания не существовала, это первый пользователь компании
                logger.debug(
                    f"Компания для чата {chat_id} не найдена. Устанавливаем онбординг для {telegram_user.full_name}.")

                # Привязка состояния к добавленному пользователю
                await state.storage.set_state(
                    key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                    state=OnboardingState.waiting_for_company_name
                )
                await state.storage.set_data(
                    key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                    data={"company_id": user.company_id}
                )

                # Проверяем состояние для пользователя
                current_state = await state.storage.get_state(
                    key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id)
                )
                logger.debug(f"Состояние для {telegram_user.full_name}: {current_state}")

                # Отправляем сообщение о начале онбординга в общий чат
                await event.bot.send_message(
                    chat_id=chat_id,  # Сообщение отправляется в общий чат
                    text=(
                        f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                        "Давайте начнем с базовой информации.\nВведите название вашей компании."
                    )
                )
            else:
                # Приветственное сообщение для последующих пользователей
                logger.debug(
                    f"Компания для чата {chat_id} уже существует. Пользователь {telegram_user.full_name} добавлен.")
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
    # Проверяем, является ли отправитель ботом
    if message.from_user and message.from_user.is_bot:
        # Игнорируем сообщения от бота
        return

    current_state = await state.get_state()
    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {current_state}")

    # Обработка системных сообщений
    if message.content_type in {ContentType.NEW_CHAT_MEMBERS, ContentType.LEFT_CHAT_MEMBER}:
        logger.debug("Обрабатываем системное сообщение (новые участники или выход).")
        if message.content_type == ContentType.NEW_CHAT_MEMBERS:
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

        # Обработка состояний редактирования компании
    if current_state == EditCompanyState.waiting_for_updated_info.state:
        await process_edit_company_information(message, state)
        return
    elif current_state == EditCompanyState.waiting_for_confirmation.state:
        await confirm_edit_company_information(message, state)
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
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")