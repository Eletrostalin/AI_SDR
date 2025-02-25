from datetime import datetime

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import pandas as pd
import io

from db.db import SessionLocal
from db.models import CompanyInfo
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
        # Читаем Excel без заголовков
        df = pd.read_excel(io.BytesIO(file_stream.read()), header=None)

        # Заполняем только заголовки (первые две строки), а не данные
        df.iloc[:2] = df.iloc[:2].ffill(axis=1)

        # **Шаг 1**: Берём название компании **из B2 (df.iloc[1,1])**
        company_name = str(df.iloc[1, 1]).strip()

        if not company_name:
            await message.answer("❌ Ошибка! В файле отсутствует название компании. Проверьте и загрузите заново.")
            return

        # **Шаг 2**: Формируем словарь с ответами из колонок A и C
        brief_data = {"company_name": company_name}  # Название компании отдельно

        # Получаем все заголовки вопросов из колонки A (до маппинга), фильтруем `nan`
        original_headers = [
            str(df.iloc[i, 0]).strip() for i in range(2, len(df)) if pd.notna(df.iloc[i, 0])
        ]

        for i in range(2, len(df)):  # Со строки 3 (индекс 2)
            key = str(df.iloc[i, 0]).strip()  # Вопрос из колонки A
            value = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else None  # Колонка C

            if key and value:  # Пропускаем пустые строки
                brief_data[key] = value

        logger.debug(f"Исходные данные перед маппингом: {brief_data}")

        # **Шаг 3**: Переименовываем ключи (из "Вопросов" в нужные поля БД)
        renamed_data = {COLUMN_MAPPING.get(k, k): v for k, v in brief_data.items()}

        # **Шаг 4**: Загружаем недостающие поля из FSM**
        data = await state.get_data()
        old_missing_fields = set(data.get("missing_fields", []))

        # **Шаг 5**: Определяем недостающие ключи, исключая `nan`
        new_missing_fields = {k for k in original_headers if k not in brief_data and k.lower() != "nan"}

        if new_missing_fields:
            logger.warning(f"❌ В файле всё ещё не хватает данных: {new_missing_fields}")

            await state.update_data(brief_data=renamed_data, missing_fields=list(new_missing_fields))
            await state.set_state(OnboardingState.missing_fields)

            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="Пропустить")], [types.KeyboardButton(text="Заполнить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )

            await message.answer(
                f"⚠️ В файле всё ещё не хватает следующих данных:\n\n{', '.join(new_missing_fields)}\n\n"
                "Отправьте обновленный файл или нажмите ‘Пропустить’.",
                reply_markup=keyboard
            )
            return

        # **Шаг 6**: Все недостающие данные заполнены → очищаем `missing_fields`**
        await state.update_data(brief_data=renamed_data, missing_fields=[])

        # Если все поля заполнены, продолжаем обработку
        await state.set_state(OnboardingState.processing_brief)
        await message.answer("✅ Файл загружен! Обрабатываю данные...")
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

        # **Проверяем, остались ли недостающие поля**
        missing_fields = data.get("missing_fields", [])

        if missing_fields:
            logger.warning(f"❌ В файле всё ещё не хватает данных: {missing_fields}")
            await message.answer(
                f"⚠️ Всё ещё не хватает следующих данных: {', '.join(missing_fields)}\n\n"
                "Загрузите новый файл или напишите ‘Пропустить’, если хотите продолжить без них."
            )
            await state.set_state(OnboardingState.missing_fields)
            return  # Ждём новый файл

        # Логируем полный словарь после маппинга
        logger.debug(f"Полный словарь после маппинга: {brief_data}")

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

        # Логируем какие ключи были удалены
        removed_keys = set(brief_data.keys()) - set(filtered_data.keys())
        logger.debug(f"Удалены неиспользуемые ключи: {removed_keys}")

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
            filtered_data["company_id"] = company_id
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
    Подтверждает успешную обработку данных и запускает следующий этап.
    """
    await message.answer(
        "✅ Готово! Данные загружены. Теперь я знаю ключевые моменты о Вашей компании и могу персонализировать рассылки."
    )

    # Очищаем состояние после онбординга
    await state.clear()

    # Запускаем следующий модуль (загрузка email-таблицы)
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