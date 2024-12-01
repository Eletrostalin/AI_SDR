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

from handlers.campaign_handlers import process_campaign_information, confirm_campaign_creation
from handlers.company_handlers import process_company_information, confirm_company_information, \
    process_edit_company_information
from utils.states import BaseState, AddCompanyState, AddCampaignState, EditCompanyState
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

    # Исключаем сообщения без текста (например, системные уведомления или приветствия)
    if not message.text:
        logger.debug("Сообщение без текста пропущено.")
        return

    try:
        # Получаем текущее состояние пользователя
        current_state = await state.get_state()
        logger.debug(f"Текущее состояние пользователя: {current_state}")

        # Логика маршрутизации по состоянию
        if current_state is None or current_state == BaseState.default.state:
            logger.debug("Пользователь в базовом состоянии. Сообщение отправляется в классификатор.")
            try:
                classification = classify_message(message.text)
                logger.debug(f"Результат классификации: {classification}")
                await dispatch_classification(classification, message, state)
            except Exception as e:
                logger.error(f"Ошибка в классификаторе: {e}")
                await message.reply("Произошла ошибка при обработке сообщения. Попробуйте снова.")
        elif current_state == AddCompanyState.waiting_for_information.state:
            logger.debug("Пользователь в состоянии AddCompanyState:waiting_for_information. Обрабатываем сообщение.")
            await process_company_information(message, state, bot=message.bot)
        elif current_state == AddCompanyState.waiting_for_confirmation.state:
            logger.debug("Пользователь в состоянии AddCompanyState:waiting_for_confirmation. Обрабатываем сообщение.")
            await confirm_company_information(message, state)
        elif current_state == AddCampaignState.waiting_for_campaign_information.state:
            logger.debug("Пользователь в состоянии AddCampaignState:waiting_for_campaign_information. Обрабатываем сообщение.")
            await process_campaign_information(message, state, bot=message.bot)
        elif current_state == AddCampaignState.waiting_for_confirmation.state:
            logger.debug("Пользователь в состоянии AddCampaignState:waiting_for_confirmation. Обрабатываем сообщение.")
            await confirm_campaign_creation(message, state)
        elif current_state == EditCompanyState.waiting_for_updated_info.state:
            logger.debug("Пользователь в состоянии EditCompanyState:waiting_for_updated_info. Обрабатываем сообщение.")
            await process_edit_company_information(message, state, bot=message.bot)
        else:
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
        user = event.new_chat_member.user
        user_name = user.full_name or user.username or "Уважаемый пользователь"
        chat_id = event.chat.id

        logger.debug(f"Пользователь {user_name} добавлен в чат {chat_id}. Проверяем и добавляем в базу данных.")

        # Добавление пользователя и компании в базу данных
        db: Session = SessionLocal()
        try:
            user_record = create_or_get_company_and_user(db, user, chat_id)
            logger.info(f"Пользователь {user_name} с ID {user.id} добавлен в базу данных.")
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя в базу данных: {e}", exc_info=True)
        finally:
            db.close()

        # Отправка приветственного сообщения
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"👋 Добро пожаловать, {user_name}!\n\n"
            "Я бот, который поможет вам автоматизировать управление рекламными кампаниями и взаимодействие с клиентами. "
            "Вот что я могу делать для вас:\n\n"
            "🔹 **Работа с компанией**:\n"
            "   - Добавить информацию о компании: \"Добавь новую компанию\"\n"
            "   - Посмотреть данные компании: \"Покажи данные компании\"\n"
            "   - Изменить данные компании: \"Измени данные компании\"\n"
            "   - Удалить компанию: \"Удалить компанию\"\n\n"
            "🔹 **Управление кампаниями**:\n"
            "   - Создать новую кампанию: \"Создай новую кампанию\"\n"
            "   - Посмотреть список кампаний: \"Покажи мне мои кампании\"\n"
            "   - Удалить кампанию: \"Удалить рекламную кампанию\"\n\n"
            "🔹 **Работа с email-лидами**:\n"
            "   - Загрузить таблицу с лидами: \"Загрузить таблицу лидов\"\n"
            "   - Посмотреть таблицу: \"Покажи таблицу лидов\"\n"
            "   - Удалить таблицу: \"Удалить таблицу лидов\"\n"
            "   - Сегментация лидов для таргетинга: \"Сегментируй лидов\"\n\n"
            "🔹 **Шаблоны и контент-планы**:\n"
            "   - Создать шаблон письма: \"Создай новый шаблон\"\n"
            "   - Посмотреть шаблоны: \"Покажи мне шаблоны\"\n"
            "   - Удалить шаблон: \"Удалить шаблон\"\n"
            "   - Создать контент-план: \"Создай контент-план\"\n"
            "   - Посмотреть контент-планы: \"Покажи контент-планы\"\n\n"
            "🔹 **Работа с черновиками и рассылками**:\n"
            "   - Создать черновики: \"Создай черновики\"\n"
            "   - Отправить письма: \"Запусти рассылку\"\n"
            "   - Посмотреть черновики: \"Покажи мне черновики\"\n\n"
            "🔹 **Работа с входящими сообщениями**:\n"
            "   - Посмотреть входящие: \"Покажи входящие сообщения\"\n"
            "   - Создать лид из письма: \"Создай лида из письма\"\n"
            "   - Создать черновик ответа: \"Ответь на входящее\"\n\n"
            "📌 Напишите \"Помощь\", чтобы получить этот список команд в любое время.\n\n"
            "🤖 Готов помочь вам в работе!"
        )