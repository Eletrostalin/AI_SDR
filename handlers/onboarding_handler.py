from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import pandas as pd
import io

from db.db import SessionLocal
from db.models import CompanyInfo, User
from handlers.email_table_handler import handle_email_table_request
from states.states import OnboardingState

import logging

logger = logging.getLogger(__name__)
router = Router()

# Обновленный словарь мапинга
COLUMN_MAPPING = {
    "Название компании": "company_name",
    "Миссия компании": "company_mission",
    "Ценности компании": "company_values",
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


@router.callback_query(lambda c: c.data in ["skip_missing_fields", "fill_missing_fields"], OnboardingState.missing_fields)
async def handle_missing_fields_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопки "Пропустить" и "Заполнить".
    """
    await call.answer()  # Закрываем всплывающее уведомление

    if call.data == "skip_missing_fields":
        logger.info("✅ Пользователь решил пропустить недостающие поля.")
        await state.update_data(missing_fields=[])
        await state.set_state(OnboardingState.confirmation)
        await confirm_brief(call.message, state)

    elif call.data == "fill_missing_fields":
        logger.info("🔄 Пользователь хочет загрузить исправленный файл.")
        await state.set_state(OnboardingState.waiting_for_brief)
        await call.message.answer("🔄 Пожалуйста, загрузите исправленный файл с недостающими данными.")


@router.message(OnboardingState.waiting_for_brief)
async def handle_brief_upload(message: types.Message, state: FSMContext):
    """
    Обработка загруженного Excel-файла с брифом.
    """
    current_state = await state.get_state()
    logger.info(f"Обработчик загрузки брифа. Текущее состояние: {current_state}")
    await message.answer("✅ Файл загружен! Начинаю обработку...")

    if not message.document:
        await message.answer("Пожалуйста, загрузите файл в формате .xlsx.")
        return

    if not message.document.file_name.endswith(".xlsx"):
        await message.answer("Ошибка! Файл должен быть в формате .xlsx.")
        return

        # Достаем `company_id` по `telegram_id` отправителя
    db: Session = SessionLocal()
    user = db.query(User).filter_by(telegram_id=str(message.from_user.id)).first()
    db.close()

    if not user or not user.company_id:
        logger.error(f"❌ Ошибка! Не найден company_id для пользователя {message.from_user.id}.")
        await message.answer("❌ Ошибка! Вы не привязаны к компании. Попросите администратора добавить вас.")
        return

    company_id = user.company_id  # ✅ Теперь у нас есть корректный company_id

    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    file_stream = await message.bot.download_file(file.file_path)

    try:
        df = pd.read_excel(io.BytesIO(file_stream.read()), header=None)
        df.iloc[:2] = df.iloc[:2].ffill(axis=1)
        company_name = str(df.iloc[1, 1]).strip()

        if not company_name:
            await message.answer("❌ Ошибка! В файле отсутствует название компании. Проверьте и загрузите заново.")
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

        logger.info(f"Исходные данные перед маппингом: {brief_data}")

        renamed_data = {COLUMN_MAPPING.get(k, k): v for k, v in brief_data.items()}
        data = await state.get_data()
        old_missing_fields = set(data.get("missing_fields", []))
        new_missing_fields = {k for k in original_headers if k not in brief_data and k.lower() != "nan"}

        if new_missing_fields:
            logger.warning(f"⚠️ В файле всё ещё не хватает данных: {new_missing_fields}")

            await state.update_data(brief_data=renamed_data, missing_fields=list(new_missing_fields))
            await state.set_state(OnboardingState.missing_fields)

            # ✅ Используем InlineKeyboardMarkup вместо ReplyKeyboardMarkup
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Пропустить", callback_data="skip_missing_fields")],
                    [InlineKeyboardButton(text="🔄 Заполнить", callback_data="fill_missing_fields")]
                ]
            )

            await message.answer(
                f"⚠️ В файле всё ещё не хватает следующих данных:\n\n{', '.join(new_missing_fields)}\n\n"
                "Выберите действие:",
                reply_markup=keyboard
            )
            return

        await state.update_data(company_id=company_id, brief_data=renamed_data, missing_fields=[])
        await state.set_state(OnboardingState.processing_brief)
        await process_brief(message, state)
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке файла. Проверьте его и попробуйте снова.")


async def process_brief(message: types.Message, state: FSMContext):
    """
    Обрабатывает данные брифа и сохраняет в базу данных.
    """
    try:
        data = await state.get_data()
        logger.info(f"Полученные данные из FSM перед обработкой: {data}")

        company_id = data.get("company_id")
        brief_data = data.get("brief_data", {})

        if not company_id:
            await message.answer("❌ Ошибка! Не найден company_id. Попробуйте загрузить файл заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        if not brief_data:
            await message.answer("❌ Ошибка! Данные брифа не найдены. Попробуйте загрузить файл заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        missing_fields = data.get("missing_fields", [])

        if missing_fields:
            logger.warning(f"В файле всё ещё не хватает данных: {missing_fields}")
            await message.answer(
                f"⚠️ Всё ещё не хватает следующих данных: {', '.join(missing_fields)}\n\n"
                "Загрузите новый файл или напишите ‘Пропустить’, если хотите продолжить без них."
            )
            await state.set_state(OnboardingState.missing_fields)
            return

        logger.info(f"Полный словарь после маппинга: {brief_data}")
        brief_data = {str(k): v for k, v in brief_data.items()}

        company_name = brief_data.get("company_name", "").strip()
        if not company_name:
            await message.answer("❌ Ошибка! Название компании отсутствует. Проверьте файл и загрузите заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        logger.info(f"Данные перед сохранением в БД: {brief_data}")
        allowed_keys = set(COLUMN_MAPPING.values())
        filtered_data = {k: v for k, v in brief_data.items() if k in allowed_keys}
        removed_keys = set(brief_data.keys()) - set(filtered_data.keys())
        logger.info(f"Удалены неиспользуемые ключи: {removed_keys}")

        db: Session = SessionLocal()
        existing_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()

        if existing_info:
            logger.info(f"Обновляем данные компании ID: {company_id}")
            for key, value in filtered_data.items():
                setattr(existing_info, key, value)
            existing_info.updated_at = datetime.utcnow()
        else:
            logger.info(f"Создаём новую запись для компании ID: {company_id}")
            filtered_data["company_id"] = company_id
            filtered_data["created_at"] = datetime.utcnow()
            filtered_data["updated_at"] = datetime.utcnow()
            new_info = CompanyInfo(**filtered_data)
            db.add(new_info)

        db.commit()
        db.close()

        logger.info(f"Сохранённый бриф: {filtered_data}")
        await state.set_state(OnboardingState.confirmation)
        await confirm_brief(message, state)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных брифа: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке данных. Проверьте файл и попробуйте снова.")


async def confirm_brief(message: types.Message, state: FSMContext):
    """
    Подтверждает успешную обработку данных и запускает следующий этап.
    """
    await message.answer(
        "✅ Готово! Данные загружены. Теперь я знаю ключевые моменты о Вашей компании и могу персонализировать рассылки."
    )

    logger.info("Состояние онбординга очищено. Переход к следующему этапу.")
    await state.clear()
    await handle_email_table_request(message, state)


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