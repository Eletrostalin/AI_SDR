from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import pandas as pd
import io

from db.db import SessionLocal
from db.models import CompanyInfo
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
    "Наличие доставки / Географический охват": "delivery_availability_geographical_coverage",
    "Часто задаваемые вопросы (FAQ) с ответами": "frequently_asked_questions_with_answers",
    "Типичные возражения клиентов и ответы на них": "common_customer_objections_and_responses",
    "Примеры успешных кейсов": "successful_case_studies",
    "Прочее": "additional_information",
    "Нет нужного поля? Напишите ниже, нам важно ваше мнение": "missing_field_feedback",
}

@router.message(OnboardingState.waiting_for_brief)
async def handle_brief_upload(message: types.Message, state: FSMContext):
    """
    Обработка загруженного Excel-файла с брифом.
    """
    if not message.document:
        await message.answer("Пожалуйста, загрузите файл в формате .xlsx.")
        return

    if not message.document.file_name.endswith(".xlsx"):
        await message.answer("Ошибка! Файл должен быть в формате .xlsx.")
        return

    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    file_stream = await message.bot.download_file(file.file_path)

    try:
        # Читаем Excel в DataFrame
        df = pd.read_excel(io.BytesIO(file_stream.read()))
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        df = df.fillna("")  # Заполняем пустые значения

        # Проверяем обязательное поле
        if "company_name" not in df.columns or df["company_name"].isnull().all():
            await message.answer("Ошибка! В файле отсутствует название компании. Проверьте и загрузите заново.")
            return

        company_name = df["company_name"].iloc[0]
        db: Session = SessionLocal()
        existing_company = db.query(CompanyInfo).filter_by(company_name=company_name).first()

        if existing_company:
            logger.info(f"Компания {company_name} уже существует. Обновляем данные.")
            for key, value in df.to_dict(orient="records")[0].items():
                setattr(existing_company, key, value)
        else:
            logger.info(f"Создаем новую компанию: {company_name}")
            new_company = CompanyInfo(**df.to_dict(orient="records")[0])
            db.add(new_company)

        db.commit()
        db.close()

        await message.answer("✅ Данные загружены! Теперь вы можете работать с ботом.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await message.answer("Ошибка при обработке файла. Проверьте его и попробуйте снова.")
