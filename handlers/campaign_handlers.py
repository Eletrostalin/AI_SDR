from aiogram.filters import StateFilter
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from config import OPENAI_API_KEY
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.models import Campaigns
from promts.campaign_promt import CREATE_CAMPAIGN_PROMPT
from utils.states import AddCampaignState
from langchain_helper import LangChainHelper
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# Инициализация LangChainHelper
langchain_helper = LangChainHelper(api_key=OPENAI_API_KEY)
router = Router()


@router.message(StateFilter(None))  # Обработчик начала добавления кампании
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления кампании.
    """
    await message.reply("Пожалуйста, отправьте информацию о вашей кампании (текст с описанием, названием и параметрами).")
    await state.set_state(AddCampaignState.waiting_for_campaign_information)


@router.message(StateFilter(AddCampaignState.waiting_for_campaign_information))
async def process_campaign_information(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с информацией о кампании.
    """
    try:
        # Формируем промпт для обработки текста
        prompt = CREATE_CAMPAIGN_PROMPT.format(input_text=message.text)

        # Вызов модели для извлечения данных
        campaign_data = await langchain_helper.classify_request(prompt)

        # Проверяем, что модель вернула корректный результат
        if not isinstance(campaign_data, dict):
            raise ValueError("Некорректный формат данных. Попробуйте ещё раз.")

        # Сохраняем данные в состояние
        await state.update_data(campaign_data=campaign_data)

        # Формируем ответ для подтверждения
        campaign_name = campaign_data.get("campaign_name", "Название не указано")
        description = campaign_data.get("description", "Описание отсутствует")
        params = campaign_data.get("params", {})

        await message.reply(
            f"Вот что получилось:\n"
            f"Название кампании: {campaign_name}\n"
            f"Описание: {description}\n"
            f"Параметры: {params}\n"
            f"Все верно? (да/нет)"
        )
        await state.set_state(AddCampaignState.waiting_for_confirmation)
    except Exception as e:
        await message.reply(f"Ошибка обработки информации: {e}")


@router.message(StateFilter(AddCampaignState.waiting_for_confirmation))
async def confirm_campaign_creation(message: Message, state: FSMContext):
    """
    Подтверждает добавление кампании в базу данных.
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

            await message.reply("Кампания успешно создана!")
            await state.clear()
        except SQLAlchemyError as e:
            await message.reply(f"Ошибка при добавлении кампании: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        await message.reply("Добавление кампании отменено.")
        await state.clear()