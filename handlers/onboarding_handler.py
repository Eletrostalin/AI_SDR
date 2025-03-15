from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import pandas as pd
import io

from db.db import SessionLocal
from db.db_company import save_company_info
from db.models import CompanyInfo, User, EmailConnections
from handlers.email_table_handler import handle_email_table_request
from states.states import OnboardingState

import logging

logger = logging.getLogger(__name__)
router = Router()

# Обновленный словарь мапинга
COLUMN_MAPPING = {
    "Название компании": "company_name",
    "Миссия компании": "company_mission",
    "Информация о компании (миссия и ценности)": "company_values",
    "Сфера деятельности": "business_sector",
    "Адреса офисов и график работы": "office_addresses_and_hours",
    "Ссылки на ресурсы": "resource_links",
    "Целевая аудитория (B2B/B2C, ниша, география)": "target_audience_b2b_b2c_niche_geography",
    "Уникальное торговое предложение (УТП)": "unique_selling_proposition",
    "Болевые точки клиентов": "customer_pain_points",
    "Отличие от конкурентов": "competitor_differences",
    "Какие продукты и услуги продвигать": "promoted_products_and_services",
    "Наличие доставки/Географический охват": "delivery_availability_geographical_coverage",
    "Часто задаваемые вопросы (FAQ) с ответами": "frequently_asked_questions_with_answers",
    "Типичные возражения клиентов и ответы на них": "common_customer_objections_and_responses",
    "Примеры успешных кейсов": "successful_case_studies",
    "Прочее": "additional_information",
    "Нет нужного поля?! Напишите ниже, нам важно ваше мнение": "missing_field_feedback",
}



@router.callback_query(lambda c: c.data in ["skip_missing_fields", "fill_missing_fields"],
                       OnboardingState.missing_fields)
async def handle_missing_fields_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя: пропустить или загрузить исправленный файл.
    """
    await call.answer()

    if call.data == "skip_missing_fields":
        logger.info("✅ Пользователь пропустил недостающие поля.")

        # Получаем сохраненные данные из состояния
        data = await state.get_data()
        company_id = data.get("company_id")
        brief_data = data.get("brief_data", {})

        # Если нет данных, не вызываем confirm_brief(), а просим загрузить заново
        if not company_id or not brief_data:
            logger.warning("❌ Ошибка! Данные не были загружены, но пользователь решил пропустить.")
            await call.message.answer("❌ Ошибка! Данные отсутствуют. Попробуйте загрузить файл заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        # Очищаем недостающие поля и подтверждаем данные
        await state.update_data(missing_fields=[])
        await confirm_brief(call.message, state)

    elif call.data == "fill_missing_fields":
        logger.info("🔄 Пользователь загружает исправленный файл.")
        await state.set_state(OnboardingState.waiting_for_brief)
        await call.message.answer("🔄 Пожалуйста, загрузите исправленный файл с недостающими данными.")


@router.message(OnboardingState.waiting_for_brief)
async def handle_brief_upload(message: types.Message, state: FSMContext):
    """
    Обрабатывает загрузку файла и предлагает пользователю подтвердить или загрузить исправленный файл.
    """
    logger.info("📥 Обработчик загрузки брифа запущен.")

    if not message.document or not message.document.file_name.endswith(".xlsx"):
        await message.answer("❌ Ошибка! Пожалуйста, загрузите файл в формате .xlsx.")
        return

    db: Session = SessionLocal()
    user = db.query(User).filter_by(telegram_id=str(message.from_user.id)).first()
    db.close()

    if not user or not user.company_id:
        await message.answer("❌ Ошибка! Вы не привязаны к компании. Обратитесь к администратору.")
        return

    company_id = user.company_id  # ✅ company_id получен
    logger.debug(f"🔹 Найден company_id: {company_id}")

    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    file_stream = await message.bot.download_file(file.file_path)

    try:
        df = pd.read_excel(io.BytesIO(file_stream.read()), header=None)
        df.iloc[:2] = df.iloc[:2].ffill(axis=1)
        company_name = str(df.iloc[2, 2]).strip()

        if not company_name:
            await message.answer("❌ В файле отсутствует название компании. Проверьте и загрузите заново.")
            return

        brief_data = {"company_name": company_name}
        original_headers = [
            str(df.iloc[i, 0]).strip() for i in range(2, len(df)) if pd.notna(df.iloc[i, 0])
        ]

        for i in range(2, len(df)):
            key = str(df.iloc[i, 0]).strip()
            value = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else None
            if key and value:
                brief_data[key] = value

        logger.info(f"📊 Исходные данные из файла: {brief_data}")

        renamed_data = {COLUMN_MAPPING.get(k, k): v for k, v in brief_data.items()}
        missing_fields = {k for k in original_headers if k not in brief_data and k.lower() != "nan"}

        # 🔹 Сохранение данных в FSMContext
        await state.update_data(brief_data=renamed_data, company_id=company_id, missing_fields=[])
        logger.debug(f"✅ Данные успешно сохранены в FSMContext: {await state.get_data()}")

        if missing_fields:
            await state.update_data(missing_fields=list(missing_fields))
            await state.set_state(OnboardingState.missing_fields)

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Пропустить", callback_data="skip_missing_fields")],
                    [InlineKeyboardButton(text="🔄 Перезагрузить", callback_data="fill_missing_fields")]
                ]
            )

            await message.answer(
                f"⚠️ В файле не хватает данных:\n\n{', '.join(missing_fields)}\n\nВыберите действие:",
                reply_markup=keyboard
            )
            return

        # ✅ Переход к подтверждению данных
        logger.debug("🔄 Передача данных в confirm_brief")
        await confirm_brief(message, state)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке файла: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке файла. Проверьте его и попробуйте снова.")


async def confirm_brief(message: types.Message, state: FSMContext):
    """
    Подтверждает данные и сохраняет их в базу.
    Если company_id отсутствует в состоянии, повторно извлекает его из базы по chat_id.
    """
    data = await state.get_data()
    company_id = data.get("company_id")
    brief_data = data.get("brief_data", {})

    logger.debug(f"📌 Загруженные данные из FSM перед сохранением: {data}")

    # Если company_id отсутствует, пробуем получить его из базы
    if not company_id:
        logger.warning("🔄 company_id отсутствует в состоянии. Пытаемся получить из базы.")

        db: Session = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=str(message.from_user.id)).first()
            if user and user.company_id:
                company_id = user.company_id
                logger.info(f"✅ Повторно получен company_id: {company_id}")
            else:
                logger.error(f"❌ Не удалось найти company_id для telegram_id {message.from_user.id}")
                await message.answer("❌ Ошибка! Данные компании отсутствуют. Попробуйте загрузить файл заново.")
                await state.set_state(OnboardingState.waiting_for_brief)
                return
        finally:
            db.close()

    # Проверяем, есть ли данные для сохранения
    if not brief_data:
        logger.error("❌ Ошибка! Данные компании отсутствуют перед сохранением в БД.")
        await message.answer("❌ Ошибка! Данные отсутствуют. Попробуйте загрузить файл заново.")
        await state.set_state(OnboardingState.waiting_for_brief)
        return

    # 🔹 Лог перед сохранением в БД
    logger.debug(f"🛠 Передаем в БД: company_id={company_id}, brief_data={brief_data}")

    success = save_company_info(company_id, brief_data)

    if success:
        logger.info("✅ Данные компании успешно сохранены в БД.")
        await message.answer("Готово! ✅ Данные загружены. Теперь я знаю ключевые моменты о Вашей компании и могу персонализировать рассылки.")
        await handle_email_table_request(message, state)  # Переход к обработке email-таблицы
    else:
        logger.error("❌ Ошибка при сохранении в БД.")
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте позже.")


@router.message(OnboardingState.missing_fields)
async def handle_missing_fields_response(message: types.Message, state: FSMContext):
    """
    Обрабатывает ответ пользователя на запрос о недостающих полях.
    """
    response = message.text.strip().lower()

    if response == "пропустить":
        logger.info("Пользователь решил пропустить недостающие поля. Завершаем онбординг.")

        # Очищаем недостающие поля и завершаем онбординг
        await state.update_data(missing_fields=[])
        await state.set_state(OnboardingState.confirmation)

        # Переход к следующему шагу
        await confirm_brief(message, state)

    elif response == "заполнить":
        logger.info("Пользователь хочет исправить недостающие поля. Ждём новый файл.")

        await state.set_state(OnboardingState.waiting_for_brief)
        await message.answer("🔄 Пожалуйста, загрузите исправленный файл с недостающими данными.")

    else:
        await message.answer("❌ Неправильный ответ. Напишите **'Пропустить'** или **'Заполнить'**.")
