from aiogram.types import FSInputFile
from sqlalchemy.sql import text
from aiogram.filters import StateFilter
from db.db_campaign import create_campaign_and_thread
from db.segmentation import EMAIL_SEGMENT_TRANSLATIONS
from handlers.content_plan_handlers.content_plan_handlers import handle_add_content_plan
from logger import logger
from db.db import SessionLocal
from promts.campaign_promt import EMAIL_SEGMENT_COLUMNS
from states.states import AddCampaignState
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.segment_utils import extract_filters_from_text, apply_filters_to_email_table, generate_excel_from_df

router = Router()


@router.message(StateFilter(None))
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Инициирует создание рекламной кампании.
    Запрашивает у пользователя название.
    """
    await message.answer("Отлично! 🚀 Давайте настроим кампанию. Я помогу Вам на каждом этапе.")
    await message.answer("Пожалуйста, укажите название рекламной кампании 🏷️")

    await state.set_state(AddCampaignState.waiting_for_campaign_name)


@router.message(StateFilter(AddCampaignState.waiting_for_campaign_name))
async def process_campaign_name(message: Message, state: FSMContext):
    """
    Обрабатывает введенное название кампании, создаёт запись в БД и тему чата.
    """
    campaign_name = message.text.strip()

    if not campaign_name:
        await message.answer("⚠️ Название кампании не может быть пустым. Попробуйте ещё раз.")
        return

    chat_id = message.chat.id
    bot = message.bot

    try:
        with SessionLocal() as db:
            new_campaign = await create_campaign_and_thread(bot, db, chat_id, campaign_name)

            email_table = db.execute(
                text("SELECT email_table_id FROM email_tables WHERE company_id = :company_id"),
                {"company_id": new_campaign.company_id}
            ).fetchone()

            email_table_id = email_table[0] if email_table else None

        campaign_data = {
            "campaign_id": new_campaign.campaign_id,
            "campaign_name": campaign_name,
            "company_id": new_campaign.company_id,
            "email_table_id": email_table_id
        }
        await state.update_data(campaign_data=campaign_data)

        segment_columns = ", ".join(
            EMAIL_SEGMENT_TRANSLATIONS.get(col, col) for col in EMAIL_SEGMENT_COLUMNS
        )

        await message.bot.send_message(
            chat_id=chat_id,
            message_thread_id=new_campaign.thread_id,
            text=f"(Доступны только те поля, в которых заполнено хотя бы одно значение)\n\n"
                 f"🔹 {segment_columns}\n\n"
                 f"Введите ответ в формате:\n"
                 f"\nКритерий - Значение\n\n"
                 f"Вы можете выбрать одно или несколько полей.\n"
                 f"Пример:\n"
                 f"\nРегион - Москва\nИмя директора - Сергей\n"
        )

        await state.set_state(AddCampaignState.waiting_for_filters)

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(StateFilter(AddCampaignState.waiting_for_filters))
async def process_filters(message: Message, state: FSMContext):
    """
    Обрабатывает ввод фильтров сегментации с помощью модели и генерирует Excel-таблицу.
    """
    user_input = message.text.strip()

    try:
        filters = extract_filters_from_text(user_input)

        if not filters:
            await message.reply("⚠️ Не удалось определить фильтры. Попробуйте переформулировать.")
            return

        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        company_id = campaign_data.get("company_id")
        campaign_id = campaign_data.get("campaign_id")
        email_table_id = campaign_data.get("email_table_id")

        if not company_id or not campaign_id or not email_table_id:
            await message.reply("❌ Ошибка: Кампания или email-таблица не найдена.")
            return

        with SessionLocal() as db:
            filtered_df = apply_filters_to_email_table(db, email_table_id, filters)

        if filtered_df.empty:
            await message.reply("⚠️ По заданным фильтрам не найдено ни одной записи.")
            return

        excel_path = generate_excel_from_df(filtered_df, company_id, campaign_id)

        await message.reply_document(
            FSInputFile(excel_path),
            caption="📂 Готово! 📊 Сегментированная база для данной рекламной кампании подготовлена."
        )

        campaign_data["filters"] = filters
        await state.update_data(campaign_data=campaign_data)

        await message.reply("Рекламная кампания настроена. Перейдем к созданию контент-плана. Для этого ответьте на несколько вопросов")
        await handle_add_content_plan(message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки фильтров через модель: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при обработке фильтров. Попробуйте ещё раз.")


