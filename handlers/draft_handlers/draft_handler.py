import asyncio
import pandas as pd
from sqlalchemy.orm import Session

from db import db
from db.models import Templates, ContentPlan, Waves
from logger import logger
from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model


async def generate_drafts_for_wave(db_session, df, wave_id):
    """
    Генерация черновиков для волны и сохранение в Google Таблицу.

    :param db_session: Сессия БД.
    :param df: DataFrame с лидами.
    :param wave_id: ID волны рассылки.
    """
    logger.info(f"🚀 Запуск генерации черновиков для волны ID {wave_id}")

    wave = db_session.query(Waves).filter_by(wave_id=wave_id).first()
    if not wave:
        logger.error(f"❌ Ошибка: Волна с ID {wave_id} не найдена.")
        return

    logger.info(f"🌊 Волна ID {wave.wave_id} найдена. Обработка {len(df)} лидов.")

    template = db_session.query(Templates).filter_by(wave_id=wave.wave_id).first()
    if not template:
        logger.error(f"❌ Нет шаблона для волны ID {wave.wave_id}. Пропускаем.")
        return

    content_plan = db_session.query(ContentPlan).filter_by(content_plan_id=wave.content_plan_id).first()
    description = content_plan.description if content_plan else "Описание отсутствует"
    email_subject = wave.subject

    batch_size = 50
    leads_batches = [df[i:i + batch_size] for i in range(0, len(df), batch_size)]
    logger.info(f"📦 Разбивка данных: {len(leads_batches)} партий по {batch_size} лидов")

    for batch_num, batch in enumerate(leads_batches, start=1):
        logger.info(f"⚙️ Обработка партии {batch_num} из {len(leads_batches)}")

        tasks = [
            generate_draft_for_lead(template, lead, email_subject, wave.wave_id, description)
            for _, lead in batch.iterrows()
        ]

        results = await asyncio.gather(*tasks)
        successful_drafts = [res for res in results if res]

        if successful_drafts:
            logger.info(f"✅ Успешно сгенерировано {len(successful_drafts)} черновиков. Отправляем в Google Sheets.")
            append_drafts_to_sheet(successful_drafts)
        else:
            logger.warning("⚠️ Ни один черновик не был успешно создан в этой партии.")


async def generate_draft_for_lead(template, lead_data, subject, wave_id, description):
    """
    Генерирует черновик письма для лида, используя все доступные данные.

    :param template: Шаблон письма.
    :param lead_data: Данные лида (dict).
    :param subject: Тема письма.
    :param wave_id: ID волны.
    :param description: Описание контентного плана.
    :return: Словарь с черновиком.
    """
    lead_id = lead_data.get("id")
    email = lead_data.get("email")
    company_name = lead_data.get("name", "Клиент")
    region = lead_data.get("region", "не указан")
    map_registry = lead_data.get("map_registry", "не указано")
    director_name = lead_data.get("director_name", "не указан")
    director_position = lead_data.get("director_position", "не указана")
    phone_number = lead_data.get("phone_number", "не указан")
    website = lead_data.get("website", "не указан")
    primary_activity = lead_data.get("primary_activity", "не указана")
    revenue = lead_data.get("revenue", "не указана")
    employee_count = lead_data.get("employee_count", "не указано")
    branch_count = lead_data.get("branch_count", "не указано")

    logger.info(f"📝 Генерируем черновик для {company_name} (lead_id={lead_id})...")

    # Формируем промпт для модели
    prompt = f"""
    Шаблон письма:
    {template.template_content}

    Данные компании:
    - Название: {company_name}
    - Регион: {region}
    - Входит в реестр: {map_registry}
    - Директор: {director_name} ({director_position})
    - Контактный номер: {phone_number}
    - Веб-сайт: {website}
    - Основной вид деятельности: {primary_activity}
    - Выручка: {revenue}
    - Число сотрудников: {employee_count}
    - Количество филиалов: {branch_count}

    📢 Описание контентного плана:
    {description}

    🎯 Задача:
    - Напиши персонализированное письмо для компании {company_name}.
    - Сделай письмо более естественным, добавь упоминание об их деятельности ({primary_activity}).
    - Используй описание контентного плана, чтобы адаптировать текст под цель кампании.
    - Перемешай абзацы, добавь уникальное вступление.
    - Используй разные формулировки, чтобы письма не были однотипными.
    Важное замечание!! Если в каких то переменных будет None не используй их в тексте письма.
    """

    # Попытки генерации черновика (3 раза)
    for attempt in range(3):
        try:
            response = send_to_model(prompt)
            if not response:
                raise ValueError("Ответ от модели пуст")
            break
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}: Ошибка генерации для lead_id={lead_id}: {e}")
            if attempt == 2:
                logger.error(f"❌ Не удалось сгенерировать письмо для lead_id={lead_id}", exc_info=True)
                return None
            await asyncio.sleep(2)

    return {
        "wave_id": wave_id,
        "lead_id": lead_id,
        "email": email,
        "company_name": company_name,
        "subject": subject,
        "text": response.strip()
    }