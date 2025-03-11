import asyncio
import json
import random
import pandas as pd
from sqlalchemy.orm import Session

from config import DATABASE_URL
from db.models import Templates
from logger import logger
from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model

# 🔹 ID Google Таблицы
SHEET_ID = "1YXv8CcjB_iOhDKAJZMkUV7BAmKE9x1kUrsN6cCWg2I8"
SHEET_NAME = "Черновики"

# 🔹 Данные тестовых лидов
TEST_LEADS = pd.DataFrame([
    {"lead_id": 1, "email": "test1@example.com", "company_name": "ООО \"Дельтабио\"", "region": "г Москва", "revenue": 236265000, "employees": 90},
    {"lead_id": 2, "email": "test2@example.com", "company_name": "ООО \"Аркада\"", "region": "г Москва", "revenue": 223247000, "employees": 80},
    {"lead_id": 3, "email": "pros@prosv.ru", "company_name": "АО \"Издательство Просвещение\"", "region": "г Москва", "revenue": 47768612000, "employees": 700}
])

# 🔹 Данные тестовой волны
TEST_WAVE = {
    "wave_id": 22,
    "content_plan_id": 25,
    "campaign_id": 59,
    "company_id": 121,
    "send_date": "2025-03-10 00:00:00",
    "subject": "Первая волна"  # 🔹 Фиксированная тема из волны
}


async def generate_drafts_for_wave(db: Session, df, wave):
    """
    Генерация черновиков для волны и сохранение в Google Таблицу.

    :param db: Сессия БД.
    :param df: DataFrame с лидами.
    :param wave: Данные волны рассылки.
    """
    logger.info(f"🚀 Начинаем генерацию черновиков для волны ID {wave.wave_id} (кол-во лидов: {len(df)})")

    # 1️⃣ Получаем шаблон письма
    template = db.query(Templates).filter_by(wave_id=wave.wave_id).first()
    if not template:
        logger.error(f"❌ Нет шаблона для волны ID {wave.wave_id}. Пропускаем.")
        return

    email_subject = wave.subject  # 🔹 Теперь берём тему корректно

    batch_size = 50
    leads_batches = [df[i:i + batch_size] for i in range(0, len(df), batch_size)]

    for batch in leads_batches:
        tasks = []
        for _, lead in batch.iterrows():
            tasks.append(generate_draft_for_lead(template, lead, email_subject, wave.wave_id))

        results = await asyncio.gather(*tasks)

        successful_drafts = [res for res in results if res]
        append_drafts_to_sheet(SHEET_ID, SHEET_NAME, successful_drafts)


async def generate_draft_for_lead(template, lead_data, subject, wave_id):
    """
    Генерирует черновик письма для лида.

    :param template: Шаблон письма.
    :param lead_data: Данные лида (dict).
    :param subject: Тема письма (берётся из волны).
    :param wave_id: ID волны.
    :return: Словарь с черновиком.
    """
    lead_id = lead_data.get("lead_id")
    email = lead_data.get("email")
    company_name = lead_data.get("company_name", "Клиент")
    region = lead_data.get("region", "не указан")
    revenue = lead_data.get("revenue", "не указана")
    employees = lead_data.get("employees", "не указано")

    logger.info(f"📝 Генерируем черновик для {company_name} (lead_id={lead_id})...")

    # 📌 **Формируем продвинутый prompt для модели**
    prompt = f"""
    Шаблон письма:
    {template.template_content}

    Данные компании:
    - Название: {company_name}
    - Регион: {region}
    - Выручка: {revenue}
    - Число сотрудников: {employees}

    🎯 Задача:
    - Напиши персонализированное письмо для компании {company_name}.
    - Подстрой стиль письма под размер компании: {employees} сотрудников (малый/средний/крупный бизнес).
    - Упомяни регион компании ({region}).
    - Сделай письмо более естественным.
    - Перемешай абзацы, добавь уникальное вступление.
    - Используй разные формулировки (не копируй 1 в 1 шаблон).
    """

    # 🔹 3 попытки при ошибке модели
    for attempt in range(3):
        try:
            response = send_to_model(prompt)  # ✅ Убрали `await`, если send_to_model не async
            if not response:
                raise ValueError("Ответ от модели пуст")
            break  # Успех
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}: Ошибка генерации для lead_id={lead_id}: {e}")
            if attempt == 2:
                logger.error(f"❌ Не удалось сгенерировать письмо для lead_id={lead_id}", exc_info=True)
                return None
            await asyncio.sleep(2)

    draft = {
        "wave_id": wave_id,
        "lead_id": lead_id,
        "email": email,
        "company_name": company_name,
        "subject": subject,  # 🔹 Теперь subject передаётся в качестве аргумента и один для всех писем
        "text": response.strip()
    }

    logger.debug(f"📩 Итоговое письмо для {company_name}: {draft}")
    return draft


# 🔹 **Запуск автономного теста**
async def run_test():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # **Настройка подключения к БД**
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        await generate_drafts_for_wave(db, TEST_LEADS, TEST_WAVE)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_test())