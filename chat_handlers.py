from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import ChatMemberUpdated, Message, ContentType
from sqlalchemy.orm import Session

from classifier import classify_message
from db.db import SessionLocal
from db.db_auth import create_or_get_company_and_user
from db.models import Company
from dispatcher import dispatch_classification
from states.states import OnboardingState
from logger import logger
from states.states_handlers import handle_onboarding_states, handle_edit_company_states, \
    handle_add_email_segmentation_states, handle_add_content_plan_states, handle_add_campaign_states, \
    handle_template_states


router = Router()


# Централизованная функция создания событий
def create_event_data(event: ChatMemberUpdated | Message, new_member=None) -> dict:
    """
    Унифицирует данные для обработки событий добавления пользователей.
    """
    if isinstance(event, ChatMemberUpdated):
        # Если это объект ChatMemberUpdated
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
    elif isinstance(event, Message) and new_member:
        # Если это Message с новым участником
        return {
            "chat": event.chat,
            "new_chat_member": {
                "user": new_member,
                "status": "member",  # Статус по умолчанию
            },
            "old_chat_member": {
                "user": event.from_user,
                "status": "left",  # Симулируем предыдущее состояние
            },
            "bot": event.bot,
        }
    else:
        raise ValueError("Неподдерживаемый тип события для create_event_data")


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated | dict, state: FSMContext):
    """
    Обработчик добавления нового пользователя в чат. Поддерживает объекты и словари.
    """
    try:
        # Унификация данных
        event_data = create_event_data(event) if isinstance(event, ChatMemberUpdated) else event

        # Извлечение данных
        new_chat_member = event_data["new_chat_member"]
        old_chat_member = event_data["old_chat_member"]
        chat_id = event_data["chat"].id
        bot = event_data["bot"]
        bot_id = bot.id

        # Проверка статусов
        if new_chat_member["status"] == "member" and old_chat_member["status"] in {"left", "kicked"}:
            telegram_user = new_chat_member["user"]

            # Пропускаем добавление бота
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

                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"👋 Добро пожаловать, {telegram_user.full_name}!\n\n"
                            "Я ваш виртуальный сотрудник AI SDR. Я помогу автоматизировать процессы продаж,\n\n"
                            "управлять базой лидов, рассылками и многое другое. Давайте начнем!"
                        )
                    )

                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "Вот мои основные функции:\n\n"
                            "• Работа с базой email для рассылок;\n"
                            "• Создание и управление персонализированными email-рассылками;\n"
                            "• Квалификация лидов с CRM;\n"
                            "• Ответы на вопросы лидов по электронной почте;\n"
                            "• Оповещение Вас о ключевых событиях, связанных с лидами."
                        )
                    )

                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "Для начала работы загрузите файл с заполненным брифом, "
                            "чтобы я мог лучше понять Ваш бизнес и качественно персонализировать рассылки."
                        )
                    )

                    await state.storage.set_state(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        state=OnboardingState.waiting_for_brief
                    )
                    await state.storage.set_data(
                        key=StorageKey(bot_id=bot_id, user_id=telegram_user.id, chat_id=chat_id),
                        data={"company_id": user.company_id}
                    )
                else:
                    logger.debug("Приветствие для существующей компании.")
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            f"👋 Добро пожаловать, {telegram_user.full_name}!\n"
                            "Вы добавлены к текущей компании."
                        )
                    )
            except Exception as e:
                logger.error(f"Ошибка обработки нового пользователя: {e}", exc_info=True)
            finally:
                db.close()

    except Exception as e:
        logger.error(f"Ошибка в greet_new_user: {e}", exc_info=True)


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
                    "chat_id": message.chat.id,
                    "new_user": {
                        "id": new_member.id,
                        "username": new_member.username,
                        "full_name": new_member.full_name,
                        "status": "member",
                    },
                    "old_status": "left",  # Предположительно, пользователь был вне чата
                    "bot_id": message.bot.id,
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
    elif current_state.startswith("TemplateStates:"):  # <=== Добавляем обработку шаблонов
        await handle_template_states(message, state, current_state)
    else:
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")
        await message.reply("Непонятное состояние. Попробуйте ещё раз или свяжитесь с поддержкой.")

