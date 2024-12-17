from aiogram import Router
from aiogram.exceptions import TelegramMigrateToChat, TelegramForbiddenError
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, ChatMemberUpdated, ContentType, ChatMemberLeft
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from aiogram.filters import Command


from admin.ThreadManager import create_new_thread
from bot import bot
from classifier import classify_message
from db.db import SessionLocal
from db.db_auth import create_or_get_company_and_user
from db.db_thread import save_thread_to_db
from db.models import Company
from dispatcher import dispatch_classification
import logging

from states.states import OnboardingState
from states.states_handlers import handle_add_campaign_states, handle_edit_company_states, handle_onboarding_states, \
    handle_add_email_segmentation_states, handle_add_content_plan_states

logger = logging.getLogger(__name__)
router = Router()


# Централизованная функция создания событий
def create_event_data_from_object(event: ChatMemberUpdated) -> dict:
    """
    Преобразует объект ChatMemberUpdated в словарь для унифицированной обработки.
    """
    return {
        "chat": event.chat,
        "new_chat_member": {
            "user": event.new_chat_member.user,
            "status": event.new_chat_member.status,
        },
        "old_chat_member": {
            "user": event.old_chat_member.user,
            "status": event.old_chat_member.status,
        },
        "bot": event.bot,
    }


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат. Поддерживает словари и объекты.
    """
    try:
        # Конвертация объекта в словарь, если это объект
        if isinstance(event, ChatMemberUpdated):
            event_data = create_event_data_from_object(event)
        else:
            event_data = event  # Если уже словарь, используем напрямую

        # Извлекаем данные
        new_chat_member = event_data["new_chat_member"]
        old_chat_member = event_data["old_chat_member"]
        chat_id = event_data["chat"].id
        bot = event_data["bot"]
        bot_id = bot.id

        # Проверка статусов и пропуск добавления самого бота
        if new_chat_member["status"] == "member" and old_chat_member["status"] in {"left", "kicked"}:
            telegram_user = new_chat_member["user"]

            if telegram_user.id == bot_id:
                logger.debug("Бот добавлен в чат. Пропускаем обработку.")
                return

            logger.debug(f"Новый пользователь {telegram_user.full_name} добавлен в чат {chat_id}.")
            db: Session = SessionLocal()
            try:
                # Проверяем существование компании
                existing_company = db.query(Company).filter_by(chat_id=str(chat_id)).first()

                # Создаём или получаем компанию и пользователя
                user = create_or_get_company_and_user(db, telegram_user, chat_id)

                if not existing_company:
                    logger.debug(f"Компания для чата {chat_id} не найдена. Устанавливаем онбординг.")
                    await state.storage.set_state(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        state=OnboardingState.waiting_for_company_name
                    )
                    await state.storage.set_data(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        data={"company_id": user.company_id}
                    )
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                            "Давайте начнем с базовой информации.\nВведите название вашей компании."
                        )
                    )
                else:
                    logger.debug("Приветствие для существующей компании.")
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                            "Вы добавлены к текущей компании. Напишите 'Помощь', чтобы узнать, что я могу делать."
                        )
                    )
            except Exception as e:
                logger.error(f"Ошибка при обработке нового пользователя: {e}", exc_info=True)
            finally:
                db.close()
    except Exception as e:
        logger.error(f"Ошибка в greet_new_user: {e}", exc_info=True)


@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Обработчик всех сообщений в чате.
    """
    # Игнорируем сообщения от ботов
    if message.from_user and message.from_user.is_bot:
        return

    current_state = await state.get_state()
    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {current_state}")

    # Обработка системных сообщений
    if message.content_type == ContentType.NEW_CHAT_MEMBERS:
        logger.debug("Обрабатываем добавление новых участников.")
        for new_member in message.new_chat_members:
            event_data = create_event_data(message, new_member)
            await greet_new_user(event_data, state)
        return

    # Обработка выхода пользователей
    if message.content_type == ContentType.LEFT_CHAT_MEMBER:
        logger.debug(f"Пользователь покинул чат: {message.left_chat_member.full_name}")
        return

    # Если состояние отсутствует, классифицируем сообщение
    if current_state is None:
        logger.debug("Состояние отсутствует. Классифицируем сообщение.")
        try:
            classification = classify_message(message.text)
            await dispatch_classification(classification, message, state)
        except Exception as e:
            logger.error(f"Ошибка классификации сообщения: {e}", exc_info=True)
            await message.reply("Произошла ошибка при обработке сообщения.")
        return

    # Маршрутизация по состояниям
    if current_state.startswith("OnboardingState:"):
        await handle_onboarding_states(message, state, current_state)
    elif current_state.startswith("EditCompanyState:"):
        await handle_edit_company_states(message, state, current_state)
    elif current_state.startswith("AddCampaignState:"):
        await handle_add_campaign_states(message, state, current_state)
    elif current_state.startswith("AddContentPlanState:"):
        await handle_add_content_plan_states(message, state, current_state)
    elif current_state.startswith("AddEmailSegmentationState:"):
        await handle_add_email_segmentation_states(message, state, current_state)
    else:
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение проигнорировано.")
        await message.reply("Неизвестное состояние. Попробуйте снова или обратитесь в поддержку.")

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