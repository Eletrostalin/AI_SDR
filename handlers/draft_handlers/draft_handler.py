import asyncio
import json
from sqlalchemy.orm import Session

from db.models import Templates
from logger import logger
from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model

# 🔹 ID Google Таблицы (возьми из ссылки)
SHEET_ID = "1YXv8CcjB_iOhDKAJZMkUV7BAmKE9x1kUrsN6cCWg2I8"
SHEET_NAME = "Черновики"  # Название листа в Google Таблице


async def generate_drafts_for_wave(db: Session, df, wave):
    """
    Генерация черновиков для волны и сохранение в Google Таблицу.

    :param db: Сессия БД.
    :param df: DataFrame с лидами.
    :param wave: Объект волны рассылки.
    """
    logger.info(f"🚀 Начинаем генерацию черновиков для волны ID {wave.wave_id} (кол-во лидов: {len(df)})")

    # 1️⃣ Получаем шаблон письма для этой волны
    template = db.query(Templates).filter_by(content_plan_id=wave.content_plan_id).first()
    if not template:
        logger.error(f"❌ Нет шаблона для волны ID {wave.wave_id}. Пропускаем.")
        return

    # 🔹 Берем тему письма из `wave.subject`
    email_subject = wave.subject

    # 2️⃣ Разбиваем лидов на батчи
    batch_size = 50
    leads_batches = [df[i:i + batch_size] for i in range(0, len(df), batch_size)]

    for batch in leads_batches:
        tasks = []
        for _, lead in batch.iterrows():
            tasks.append(generate_draft_for_lead(template, lead, email_subject, wave.wave_id))

        # ✅ Запускаем генерацию для всех лидов в батче
        results = await asyncio.gather(*tasks)

        # ✅ Фильтруем успешные черновики (если генерация не сломалась)
        successful_drafts = [res for res in results if res]

        # ✅ Сохраняем в Google Sheets
        append_drafts_to_sheet(SHEET_ID, SHEET_NAME, successful_drafts)


async def generate_draft_for_lead(template, lead_data, subject, wave_id):
    """
    Генерирует черновик письма для лида.

    :param template: Шаблон письма.
    :param lead_data: Данные лида (dict).
    :param subject: Тема письма (одинаковая для всей волны).
    :param wave_id: ID волны.
    :return: Словарь с черновиком.
    """
    lead_id = lead_data.get("lead_id")
    email = lead_data.get("email")
    company_name = lead_data.get("company_name", "Клиент")

    logger.info(f"📝 Генерируем черновик для lead_id={lead_id}...")

    prompt = f"""
    Шаблон письма:
    {template.text}

    Данные лида:
    {json.dumps(lead_data, ensure_ascii=False, indent=2)}

    Задача: Напиши персонализированное письмо на основе шаблона и данных лида.
    """

    # 🔹 3 попытки при ошибке модели
    for attempt in range(3):
        try:
            response = await send_to_model()  # Вызов модели
            break  # Успех
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}: Ошибка генерации для lead_id={lead_id}: {e}")
            if attempt == 2:
                logger.error(f"❌ Не удалось сгенерировать письмо для lead_id={lead_id}", exc_info=True)
                return None
            await asyncio.sleep(2)

    # ✅ Формируем черновик
    draft = {
        "wave_id": wave_id,
        "lead_id": lead_id,
        "email": email,
        "company_name": company_name,
        "subject": subject,  # ✅ Фиксированная тема для всех писем в волне
        "text": response.strip()
    }

    return draft