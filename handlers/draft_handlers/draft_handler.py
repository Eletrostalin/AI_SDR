from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session

from db.db import SessionLocal
from db.db_campaign import get_campaign_by_thread_id
from db.models import Templates, Waves, ContentPlan, Campaigns, EmailTable, Company
import logging

from states.states import DraftStates

logger = logging.getLogger(__name__)
router = Router()


def get_company_tables_by_campaign(campaign):
    pass


@router.message(Command("add_drafts"))
async def add_drafts(message: types.Message, state: FSMContext):
    """
    Начинает процесс создания черновиков. Определяет кампанию, компанию и связанные таблицы.
    """
    thread_id = message.message_thread_id  # Определяем thread_id
    user_id = message.from_user.id

    logger.info(f"📨 [User {user_id}] отправил команду /add_drafts в теме {thread_id}")

    # Получаем кампанию
    campaign = get_campaign_by_thread_id(thread_id)
    if not campaign:
        await message.reply("Кампания, связанная с этим чатом, не найдена.")
        return

    # Получаем company_id и список tables_name
    company_id, tables_names = get_company_tables_by_campaign(campaign)
    if not company_id or not tables_names:
        await message.reply("Не найдены таблицы, связанные с вашей компанией.")
        return

    # Сохраняем данные в FSMContext
    await state.update_data(
        campaign_id=campaign.campaign_id,
        company_id=company_id,
        tables_names=tables_names
    )

    # Логируем сохраненные данные
    logger.info(f"✅ [User {user_id}] Определены кампания {campaign.campaign_id} и company_id {company_id}")

    # 📌 **Следующий шаг: предложить пользователю выбрать контент-план**
    db = SessionLocal()
    try:
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign.campaign_id).all()
        if not content_plans:
            await message.reply("Для этой кампании нет доступных контент-планов.")
            return

        # Создаем кнопки для выбора контент-плана
        keyboard = InlineKeyboardBuilder()
        for content_plan in content_plans:
            keyboard.add(InlineKeyboardButton(
                text=content_plan.description or f"Контент-план {content_plan.content_plan_id}",
                callback_data=f"select_content_plan:{content_plan.content_plan_id}"
            ))

        await message.reply("Выберите контентный план:", reply_markup=keyboard.as_markup())

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при получении контент-планов: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


# 📌 2. Выбор волны контент-плана
@router.callback_query(lambda c: c.data.startswith("select_content_plan:"))
async def select_content_plan(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор контент-плана и предлагает выбрать волну.
    """
    content_plan_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"📌 [User {user_id}] выбрал контент-план {content_plan_id}")

    try:
        # Получаем контент-план
        content_plan = db.query(ContentPlan).filter_by(content_plan_id=content_plan_id).first()
        if not content_plan:
            await callback.message.reply("Выбранный контентный план не найден.")
            return

        # Получаем список волн, связанных с этим контентным планом
        waves = db.query(Waves).filter_by(content_plan_id=content_plan_id).all()

        if not waves:
            await callback.message.reply("В этом контентном плане нет доступных волн.")
            return

        # Создаем инлайн-кнопки для выбора волны
        keyboard = InlineKeyboardBuilder()
        for wave in waves:
            keyboard.add(InlineKeyboardButton(
                text=f"{wave.subject} ({wave.send_date.strftime('%Y-%m-%d')})",
                callback_data=f"select_wave:{wave.wave_id}"
            ))

        # Отправляем пользователю выбор волн
        await callback.message.reply("Выберите волну для создания черновиков:", reply_markup=keyboard.as_markup())

        # Логируем сохраненные данные
        logger.info(f"✅ [User {user_id}] Контент-план {content_plan_id} содержит {len(waves)} волн.")

        # Сохраняем content_plan_id в FSM
        await state.update_data(content_plan_id=content_plan_id)

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при выборе контент-плана {content_plan_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()