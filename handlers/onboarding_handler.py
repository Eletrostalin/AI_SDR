from datetime import datetime

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
    current_state = await state.get_state()
    logger.debug(f"Обработчик загрузки брифа. Текущее состояние: {current_state}")

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
        # Читаем Excel без заголовков (чтобы учесть объединение ячеек)
        df = pd.read_excel(io.BytesIO(file_stream.read()), header=None)

        # Логируем заголовки и первую строки
        logger.debug(f"Первая строка (заголовки): {df.iloc[0].tolist()}")
        logger.debug(f"Вторая строка (название компании): {df.iloc[1].tolist()}")

        # Заполняем объединённые ячейки (переносим значения вправо)
        df = df.ffill(axis=1)

        # **Шаг 1**: Берём название компании **из B2 (df.iloc[1,1])**
        company_name = str(df.iloc[1, 1]).strip()

        if not company_name:
            await message.answer(
                "❌ Ошибка! В файле отсутствует название компании. Проверьте и загрузите заново."
            )
            return

        # **Шаг 2**: Формируем словарь с ответами из колонок A и C
        brief_data = {"company_name": company_name}  # Название компании отдельно

        for i in range(2, len(df)):  # Со строки 3 (индекс 2)
            key = str(df.iloc[i, 0]).strip()  # Вопрос из колонки A
            value = str(df.iloc[i, 2]).strip()  # Ответ из колонки C
            if key and value:  # Пропускаем пустые строки
                brief_data[key] = value

        # **Шаг 3**: Переименовываем ключи (из "Вопросов" в нужные поля БД)
        renamed_data = {COLUMN_MAPPING.get(k, k): v for k, v in brief_data.items()}

        # Логируем обработанные данные
        logger.debug(f"Обработанные данные: {renamed_data}")

        # **Шаг 4**: Сохраняем в FSMContext
        await state.update_data(brief_data=renamed_data)
        await state.set_state(OnboardingState.processing_brief)
        await message.answer("✅ Файл загружен! Обрабатываю данные...")

        # Передаём в обработчик БД
        await process_brief(message, state)

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке файла. Проверьте его и попробуйте снова.")


async def process_brief(message: types.Message, state: FSMContext):
    """
    Обрабатывает данные брифа и сохраняет в базу данных.
    """
    try:
        # Загружаем данные из FSMContext
        data = await state.get_data()
        logger.debug(f"Полученные данные из FSM перед обработкой: {data}")

        company_id = data.get("company_id")  # Достаём company_id
        brief_data = data.get("brief_data", {})

        if not company_id:
            await message.answer("❌ Ошибка! Не найден company_id. Попробуйте загрузить файл заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        if not brief_data:
            await message.answer("❌ Ошибка! Данные брифа не найдены. Попробуйте загрузить файл заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        # Приводим все ключи к строкам (на случай, если что-то сломалось)
        brief_data = {str(k): v for k, v in brief_data.items()}

        # Проверяем наличие названия компании
        company_name = brief_data.get("company_name", "").strip()
        if not company_name:
            await message.answer("❌ Ошибка! Название компании отсутствует. Проверьте файл и загрузите заново.")
            await state.set_state(OnboardingState.waiting_for_brief)
            return

        # Логируем данные перед сохранением
        logger.debug(f"Данные перед сохранением в БД: {brief_data}")

        # Оставляем только ключи, которые есть в модели `CompanyInfo`
        allowed_keys = set(COLUMN_MAPPING.values())
        filtered_data = {k: v for k, v in brief_data.items() if k in allowed_keys}

        db: Session = SessionLocal()

        # **Ищем информацию о компании по `company_id`, а не по `company_name`**
        existing_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()

        if existing_info:
            logger.info(f"Обновляем данные компании ID: {company_id}")
            for key, value in filtered_data.items():
                setattr(existing_info, key, value)
            existing_info.updated_at = datetime.utcnow()
        else:
            logger.info(f"Создаём новую запись для компании ID: {company_id}")
            filtered_data["company_id"] = company_id  # **Добавляем company_id**
            filtered_data["created_at"] = datetime.utcnow()
            filtered_data["updated_at"] = datetime.utcnow()

            new_info = CompanyInfo(**filtered_data)
            db.add(new_info)

        db.commit()
        db.close()

        logger.debug(f"✅ Сохранённый бриф: {filtered_data}")

        await state.set_state(OnboardingState.confirmation)
        await confirm_brief(message, state)

    except Exception as e:
        logger.error(f"Ошибка при сохранении данных брифа: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке данных. Проверьте файл и попробуйте снова.")


async def confirm_brief(message: types.Message, state: FSMContext):
    """
    Подтверждает успешную обработку данных.
    """
    await message.answer("✅ Данные загружены! Теперь вы можете работать с ботом.")
    await state.clear()