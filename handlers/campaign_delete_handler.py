from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.future import select

from db.db import SessionLocal
from db.models import Campaigns, Company
from utils.states import DeleteCampaignState


async def handle_delete_campaign_request(message: types.Message, state: FSMContext):
    """
    Начинает процесс удаления кампании: отправляет список доступных кампаний пользователю.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    db = SessionLocal()

    try:
        # Получаем company_id пользователя по chat_id
        query = select(Company.company_id).where(Company.chat_id == str(chat_id))
        result = db.execute(query)
        company_id = result.scalar_one_or_none()

        if not company_id:
            await message.reply("Компания для вашего аккаунта не найдена.")
            return

        # Получаем все активные кампании, привязанные к компании
        query = select(Campaigns).where(
            Campaigns.company_id == company_id,
            Campaigns.status_for_user == True
        )
        result = db.execute(query)
        campaigns = result.scalars().all()

        if not campaigns:
            await message.reply("У вас нет активных кампаний для удаления.")
            return

        # Создаем кнопки с названиями кампаний
        buttons = [[KeyboardButton(text=campaign.campaign_name)] for campaign in campaigns]
        keyboard = ReplyKeyboardMarkup(
            keyboard=buttons,
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await message.reply("Выберите кампанию, которую хотите удалить:", reply_markup=keyboard)
        await state.update_data(company_id=company_id)
        await state.set_state(DeleteCampaignState.waiting_for_campaign_selection)

    finally:
        db.close()


async def handle_campaign_selection(message: types.Message, state: FSMContext):
    """
    Обрабатывает выбор кампании для удаления.
    """
    campaign_name = message.text

    # Получаем company_id из состояния
    data = await state.get_data()
    company_id = data.get("company_id")
    db = SessionLocal()

    try:
        # Ищем кампанию по названию и company_id
        query = select(Campaigns).where(
            Campaigns.company_id == company_id,
            Campaigns.campaign_name == campaign_name,
            Campaigns.status_for_user == True
        )
        result = db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            await message.reply("Кампания с таким названием не найдена. Пожалуйста, выберите из предложенного списка.")
            return

        # Сохраняем ID кампании в состоянии
        await state.update_data(campaign_id=campaign.campaign_id)

        await message.reply(f"Вы уверены, что хотите удалить кампанию '{campaign_name}'? Напишите 'Да' для подтверждения.")
        await state.set_state(DeleteCampaignState.waiting_for_campaign_confirmation)

    finally:
        db.close()


async def handle_campaign_deletion_confirmation(message: types.Message, state: FSMContext):
    """
    Подтверждает удаление кампании и изменяет её статус.
    """
    if message.text.lower() != "да":
        await message.reply("Удаление кампании отменено.")
        await state.clear()
        return

    # Получаем ID кампании из состояния
    data = await state.get_data()
    campaign_id = data.get("campaign_id")
    db = SessionLocal()

    try:
        # Ищем кампанию по ID
        query = select(Campaigns).where(Campaigns.campaign_id == campaign_id)
        result = db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            await message.reply("Произошла ошибка. Кампания не найдена.")
            await state.clear()
            return

        # Обновляем статус кампании
        campaign.status_for_user = False
        db.add(campaign)
        db.commit()

        await message.reply(f"Кампания '{campaign.campaign_name}' успешно удалена.")
        await state.clear()

    finally:
        db.close()