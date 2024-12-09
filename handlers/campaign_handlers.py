from aiogram.filters import StateFilter
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.ThreadManager import create_thread
from db.db_campaign import get_campaigns_by_company_id
from logger import logger
from config import OPENAI_API_KEY
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.models import Campaigns, ChatThread
from utils.google_doc import create_google_sheets_table
from utils.states import AddCampaignState, BaseState
from classifier import extract_campaign_data_with_validation
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.utils import process_message

router = Router()

# Обработчик начала добавления кампании
@router.message(StateFilter(None))
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления кампании.
    """
    await message.reply("Пожалуйста, отправьте информацию о вашей кампании (текст с описанием, названием и параметрами).")
    await state.set_state(AddCampaignState.waiting_for_campaign_information)


# Обработчик получения информации о кампании
@router.message(StateFilter(AddCampaignState.waiting_for_campaign_information))
async def process_campaign_information(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с информацией о кампании, отправляет данные модели
    для формирования JSON и сохраняет их в FSMContext.
    """
    try:
        bot = message.bot  # Получаем объект бота из сообщения
        # Извлечение информации из сообщения
        extracted_info = await process_message(message, bot)

        if extracted_info["type"] == "error":
            await message.reply(f"Ошибка: {extracted_info['message']}")
            return

        # Получаем JSON с данными о кампании через OpenAI
        campaign_data = await extract_campaign_data_with_validation(extracted_info['content'], state, message)

        if not campaign_data:
            # Если данные неполные, ждем уточнения
            return

        # Проверяем, что campaign_data является корректным
        if not isinstance(campaign_data, dict):
            raise ValueError("Получены некорректные данные от модели. Ожидается JSON.")

        # Сохраняем данные в состояние
        await state.update_data(campaign_data=campaign_data)

        # Формируем строку для пользователя
        campaign_name = campaign_data.get("campaign_name", "Название не указано")
        description = campaign_data.get("description", "Описание отсутствует")
        params = campaign_data.get("params", {})

        await message.reply(
            f"Мы интерпретировали вашу информацию следующим образом:\n"
            f"Название кампании: {campaign_name}\n"
            f"Описание: {description}\n"
            f"Параметры: {params}\n"
            f"Все верно? (да/нет)"
        )

        # Устанавливаем состояние ожидания подтверждения
        await state.set_state(AddCampaignState.waiting_for_confirmation)
        logger.debug(f"Состояние установлено: {await state.get_state()}")

    except Exception as e:
        logger.error(f"Ошибка обработки данных кампании: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке данных кампании. Попробуйте снова.")


# Обработчик подтверждения кампании
@router.message(StateFilter(AddCampaignState.waiting_for_confirmation))
async def confirm_campaign_creation(message: Message, state: FSMContext):
    """
    Подтверждает добавление кампании в базу данных и создает тему в чате.
    """
    if message.text.lower() in ["да", "верно"]:
        # Получаем данные из состояния
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data")

        # Открываем сессию для работы с базой данных
        db = SessionLocal()
        try:
            # Получаем компанию по chat_id
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                await message.reply("Ошибка: Компания не найдена.")
                return

            # Создаем новую кампанию
            new_campaign = Campaigns(
                company_id=company.company_id,
                campaign_name=campaign_data["campaign_name"],
                start_date=func.now(),
                params=campaign_data.get("params", {})
            )
            db.add(new_campaign)
            db.commit()

            # Создаем тему в чате
            bot = message.bot  # Получаем объект бота
            thread_name = f"Кампания: {campaign_data['campaign_name']}"  # Название темы
            created_thread_id = await create_thread(bot, chat_id, thread_name)  # Функция для создания темы

            # Записываем информацию о созданной теме в базу данных
            if created_thread_id:
                new_thread = ChatThread(
                    chat_id=chat_id,
                    thread_id=created_thread_id,
                    thread_name=thread_name
                )
                db.add(new_thread)
                db.commit()

                await message.reply(
                    f"Кампания успешно создана, и тема '{thread_name}' была добавлена в чат!"
                )
            else:
                await message.reply("Кампания успешно создана, но тема не была добавлена в чат.")

            await state.set_state(BaseState.default)
        except SQLAlchemyError as e:
            await message.reply(f"Ошибка при добавлении кампании: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"Ошибка при создании темы: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании темы в чате.")
        finally:
            db.close()
    else:
        await message.reply("Добавление кампании отменено.")
        await state.set_state(BaseState.default)

@router.message(StateFilter(AddCampaignState.waiting_for_campaign_name))
async def process_campaign_name(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с уточнением названия кампании.
    """
    campaign_name = message.text.strip()

    # Проверяем, что название кампании не пустое
    if not campaign_name:
        await message.reply("Название кампании не может быть пустым. Укажите его ещё раз.")
        return

    # Обновляем данные в состоянии FSM
    state_data = await state.get_data()
    campaign_data = state_data.get("campaign_data", {})
    campaign_data["campaign_name"] = campaign_name
    await state.update_data(campaign_data=campaign_data)

    # Формируем сообщение для подтверждения данных
    description = campaign_data.get("description", "Описание отсутствует")
    params = campaign_data.get("params", {})

    await message.reply(
        f"Название кампании: {campaign_name}\n"
        f"Описание: {description}\n"
        f"Параметры: {params}\n"
        f"Все верно? (да/нет)"
    )

    # Переводим в состояние ожидания подтверждения
    await state.set_state(AddCampaignState.waiting_for_confirmation)


async def handle_view_campaigns(message: Message, state):
    """
    Обработчик для просмотра рекламных кампаний.
    """
    chat_id = str(message.chat.id)
    db: Session = SessionLocal()

    try:
        # Получаем компанию по chat_id
        company = get_company_by_chat_id(db, chat_id)
        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return

        # Извлекаем рекламные кампании
        campaigns = get_campaigns_by_company_id(db, company.company_id)

        if not campaigns:
            await message.reply("У вас нет активных рекламных кампаний.")
            return

        # Формируем данные для таблицы Google Docs
        data = [["ID", "Название кампании", "Статус", "Дата создания", "Дата завершения"]]  # Заголовки таблицы
        data += [
            [
                campaign.campaign_id,
                campaign.campaign_name,
                campaign.status,
                campaign.created_at.strftime("%Y-%m-%d"),
                campaign.end_date.strftime("%Y-%m-%d") if campaign.end_date else "Не указана",
            ]
            for campaign in campaigns
        ]

        # Логируем сформированные данные для отладки
        logger.debug(f"Сформированные данные для Google Docs: {data}")

        # Создаем Google Doc
        google_doc_url = create_google_sheets_table(data, title=f"Рекламные кампании - {company.name}")

        # Отправляем ссылку на документ
        await message.reply(f"Ваши рекламные кампании: [Открыть документ]({google_doc_url})", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка при обработке просмотра кампаний: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса.")
    finally:
        db.close()
