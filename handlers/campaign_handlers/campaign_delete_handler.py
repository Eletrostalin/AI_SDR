from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select

from db.db import SessionLocal
from db.models import Campaigns, Company
from states.states import DeleteCampaignState


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

        # Генерируем инлайн-кнопки для кампаний
        buttons = [
            InlineKeyboardButton(
                text=campaign.campaign_name,
                callback_data=f"delete_campaign:{campaign.campaign_id}"
            ) for campaign in campaigns
        ]

        if not buttons:
            await message.reply("У вас нет доступных кампаний для удаления.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

        await message.reply("Выберите кампанию, которую хотите удалить:", reply_markup=keyboard)
        await state.update_data(company_id=company_id)

    finally:
        db.close()


async def handle_campaign_deletion_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает инлайн-кнопку для удаления кампании.
    """
    db = SessionLocal()

    try:
        # Извлекаем ID кампании из callback_data
        callback_data = callback_query.data
        if not callback_data.startswith("delete_campaign:"):
            await callback_query.answer("Неверные данные. Попробуйте снова.")
            return

        campaign_id = int(callback_data.split(":")[1])

        # Проверяем, существует ли кампания
        query = select(Campaigns).where(
            Campaigns.campaign_id == campaign_id,
            Campaigns.status_for_user == True
        )
        result = db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            await callback_query.answer("Кампания не найдена или уже удалена.", show_alert=True)
            return

        # Обновляем статус кампании
        campaign.status_for_user = False
        db.add(campaign)
        db.commit()

        await callback_query.message.reply(f"Кампания '{campaign.campaign_name}' успешно удалена.")
        await callback_query.answer("Кампания удалена.", show_alert=True)

    finally:
        db.close()