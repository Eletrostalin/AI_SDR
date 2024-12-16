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
from states.states import OnboardingState, EditCompanyState, AddCampaignState, AddEmailSegmentationState
import logging

from states.states_handlers import handle_add_campaign_states, handle_edit_company_states, handle_onboarding_states, \
    handle_add_email_segmentation_states, handle_add_content_plan_states

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
async def greet_new_user(event: dict, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат.
    """
    try:
        new_chat_member = event["new_chat_member"]
        old_chat_member = event["old_chat_member"]

        # Проверка статусов
        if new_chat_member["status"] == "member" and old_chat_member["status"] in {"left", "kicked"}:
            telegram_user = new_chat_member["user"]
            chat_id = event["chat"].id
            bot = event["bot"]
            bot_id = bot.id

            # Проверяем, чтобы добавленный пользователь не был ботом
            if telegram_user.id == bot_id:
                logger.debug("Бот добавлен в чат. Пропускаем обработку.")
                return  # Игнорируем добавление самого бота

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
                        f"Компания для чата {chat_id} не найдена. Устанавливаем онбординг для {telegram_user.full_name}."
                    )

                    # Привязка состояния к добавленному пользователю
                    await state.storage.set_state(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        state=OnboardingState.waiting_for_company_name
                    )
                    await state.storage.set_data(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        data={"company_id": user.company_id}
                    )

                    # Отправляем сообщение о начале онбординга в общий чат
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                            "Давайте начнем с базовой информации.\nВведите название вашей компании."
                        )
                    )
                else:
                    # Приветственное сообщение для последующих пользователей
                    logger.debug(
                        f"Компания для чата {chat_id} уже существует. Пользователь {telegram_user.full_name} добавлен."
                    )
                    await bot.send_message(
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
    except KeyError as e:
        logger.error(f"Ошибка в структуре события: {e}", exc_info=True)

@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Обработчик всех сообщений в чате.
    Если пользователь добавлен в чат, запускается онбординг.
    Если состояние отсутствует, устанавливается базовое состояние, и сообщение направляется в классификатор.
    """
    # Проверяем, является ли отправитель ботом
    if message.from_user and message.from_user.is_bot:
        return  # Игнорируем сообщения от бота

    current_state = await state.get_state()
    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {current_state}")

    # Обработка системных сообщений
    if message.content_type in {ContentType.NEW_CHAT_MEMBERS, ContentType.LEFT_CHAT_MEMBER}:
        logger.debug("Обрабатываем системное сообщение (новые участники или выход).")
        if message.content_type == ContentType.NEW_CHAT_MEMBERS:
            for new_member in message.new_chat_members:
                event_data = {
                    "chat": message.chat,
                    "from_user": message.from_user,
                    "new_chat_member": {
                        "user": new_member,
                        "status": "member",  # Симулируем статус
                    },
                    "old_chat_member": {
                        "user": message.from_user,
                        "status": "left",  # Симулируем предыдущее состояние
                    },
                    "bot": message.bot,
                }
                logger.debug(f"Обрабатываем добавление нового пользователя: {new_member.full_name}")
                await greet_new_user(event_data, state)
        elif message.content_type == ContentType.LEFT_CHAT_MEMBER:
            logger.debug(f"Пользователь покинул чат: {message.left_chat_member.full_name}")
        logger.debug("Системное сообщение обработано. Пропускаем обработку.")
        return

    # Если состояние не установлено, классифицируем сообщение и устанавливаем базовое состояние
    if current_state is None:
        logger.debug("Состояние отсутствует. Устанавливаем базовое состояние и классифицируем сообщение.")
        try:
            classification = classify_message(message.text)  # Классификация сообщения
            logger.debug(f"Результат классификации: {classification}")
            await dispatch_classification(classification, message, state)  # Передача в диспетчер
        except Exception as e:
            logger.error(f"Ошибка в процессе классификации: {e}", exc_info=True)
            await message.reply("Произошла ошибка при обработке вашего сообщения. Попробуйте снова.")
        return

    # Маршрутизация по состояниям
    if current_state.startswith("OnboardingState:"):
        await handle_onboarding_states(message, state, current_state)
    elif current_state.startswith("EditCompanyState:"):
        await handle_edit_company_states(message, state, current_state)
    elif current_state.startswith("AddCampaignState:"):
        await handle_add_campaign_states(message, state, current_state)
    elif current_state.startswith("AddContentPlanState:"):  # Добавлена новая ветка
        await handle_add_content_plan_states(message, state, current_state)
    elif current_state.startswith("AddEmailSegmentationState:"):
        await handle_add_email_segmentation_states(message, state, current_state)
    else:
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")
        await message.reply("Непонятное состояние. Попробуйте ещё раз или свяжитесь с поддержкой.")

