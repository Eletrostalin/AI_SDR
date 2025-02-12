import json
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.db import SessionLocal
from db.db_campaign import get_campaign_by_thread_id
from db.models import Waves, ContentPlan, Campaigns, EmailTable, Company
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("add_drafts"))
async def add_drafts(message: types.Message, state: FSMContext):
    """
    Начинает процесс создания черновиков. Определяет кампанию, компанию и связанные таблицы.
    """
    thread_id = message.message_thread_id  # Определяем thread_id
    user_id = message.from_user.id
    db: Session = SessionLocal()

    logger.info(f"📨 [User {user_id}] отправил команду /add_drafts в теме {thread_id}")

    # Получаем кампанию
    campaign = get_campaign_by_thread_id(thread_id)
    if not campaign:
        await message.reply("Кампания, связанная с этим чатом, не найдена.")
        return

    # Получаем company_id и список tables_name
    company_id, tables_names = get_company_tables_by_campaign(db, campaign)
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
                callback_data=f"select_content_plans:{content_plan.content_plan_id}"
            ))

        await message.reply("Выберите контентный план:", reply_markup=keyboard.as_markup())

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при получении контент-планов: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


# 📌 2. Выбор волны контент-плана
@router.callback_query(lambda c: c.data.startswith("select_content_plans:"))
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
                callback_data=f"select_waves:{wave.wave_id}"
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


@router.callback_query(lambda c: c.data.startswith("select_waves:"))
async def select_wave(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор волны и запускает процесс генерации черновиков.
    """
    wave_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"📌 [User {user_id}] выбрал волну {wave_id}")

    try:
        # Получаем объект волны
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            await callback.message.reply("Выбранная волна не найдена.")
            return

        # Сохраняем wave_id в FSM
        await state.update_data(wave_id=wave_id)

        # Запускаем следующий этап
        await process_email_table(callback.message, state, db)

    except Exception as e:
        logger.error(f"Ошибка в process_wave_selection: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


async def process_email_table(message: types.Message, state: FSMContext, db):
    """
    Определяет email-таблицу, принадлежащую компании, и запускает фильтрацию email'ов.
    """
    state_data = await state.get_data()
    company_id = state_data.get("company_id")

    try:
        email_table = db.query(EmailTable).filter_by(company_id=company_id).first()
        if not email_table:
            await message.reply("Не найдена email-таблица для данной компании.")
            return

        await state.update_data(email_table_id=email_table.email_table_id)
        logger.info(f"✅ Найдена email-таблица ID {email_table.email_table_id} для компании {company_id}")

        # Загружаем объект кампании
        campaign = db.query(Campaigns).filter_by(campaign_id=state_data["campaign_id"]).first()
        if not campaign:
            await message.reply("Кампания не найдена.")
            return

        # Запуск фильтрации email'ов по сегментам
        await filter_email_by_segments(campaign, email_table, db, message)

    except Exception as e:
        logger.error(f"Ошибка в process_email_table: {e}", exc_info=True)
        await message.reply("Произошла ошибка при поиске email-таблицы. Попробуйте позже.")


async def filter_email_by_segments(campaign: Campaigns, email_table: EmailTable, db: Session, message: types.Message):
    """
    Фильтрует email-адреса по сегментам кампании и логирует данные.
    """
    user_id = message.from_user.id
    segments = campaign.segments

    if not segments:
        await message.reply("Для этой кампании нет сегментации.")
        return

    try:
        segments = json.loads(segments) if isinstance(segments, str) else segments
    except json.JSONDecodeError:
        await message.reply("Ошибка в формате данных сегментации.")
        return

    logger.debug(f"📌 Значения фильтра: {segments}")

    # 🔒 Проверяем, что имя таблицы безопасное
    table_name = email_table.table_name
    if not table_name.isidentifier():
        logger.error(f"❌ Неверное имя таблицы: {table_name}")
        await message.reply("Ошибка при обработке email-таблицы.")
        return

    # 📌 Формируем безопасный SQL-запрос
    sql_query = text(f"SELECT email FROM {table_name} WHERE region = :region")

    try:
        email_records = db.execute(sql_query, {"region": segments["region"]}).fetchall()
        matching_emails = [record[0] for record in email_records]  # Извлекаем email-адреса

        count = len(matching_emails)
        logger.info(f"✅ [User {user_id}] Найдено {count} email-адресов, подходящих под сегментацию.")
        await message.reply(f"Найдено {count} email-адресов, соответствующих фильтру.")

    except Exception as e:
        logger.error(f"❌ Ошибка при фильтрации email-адресов: {e}", exc_info=True)
        await message.reply("Произошла ошибка при фильтрации email-адресов.")


def get_company_tables_by_campaign(db: Session, campaign: Campaigns):
    """
    Получает компанию по кампании и список таблиц email'ов.
    """
    company = db.query(Company).filter_by(company_id=campaign.company_id).first()
    if not company:
        return None, []

    tables_names = [table.table_name for table in db.query(EmailTable).filter_by(company_id=company.company_id).all()]
    return company.company_id, tables_names
