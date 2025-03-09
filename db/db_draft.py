import asyncio
import json
from sqlalchemy.orm import Session

from db.models import Templates
from logger import logger
import uuid

from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model

# 🔹 ID Google Таблицы (возьми из ссылки)
SHEET_ID = "1YXv8CcjB_iOhDKAJZMkUV7BAmKE9x1kUrsN6cCWg2I8"
SHEET_NAME = "Черновики"  # Название листа в Google Таблице



def generate_lead_id():
    """Генерирует уникальный lead_id."""
    return str(uuid.uuid4())  # Уникальный идентификатор


async def generate_drafts_for_wave(db: Session, df, wave):
    """ Генерация черновиков для волны. """
    logger.info(f"🚀 Начинаем генерацию черновиков для волны ID {wave.wave_id} (лидов: {len(df)})")

    template = db.query(Templates).filter_by(content_plan_id=wave.content_plan_id).first()
    if not template:
        logger.error(f"❌ Нет шаблона для волны ID {wave.wave_id}. Пропускаем.")
        return

    email_subject = wave.subject

    batch_size = 50
    leads_batches = [df[i:i + batch_size] for i in range(0, len(df), batch_size)]

    for batch in leads_batches:
        tasks = [generate_draft_for_lead(template, lead, email_subject, wave.wave_id) for _, lead in batch.iterrows()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful_drafts = [res for res in results if isinstance(res, dict)]
        append_drafts_to_sheet(SHEET_ID, SHEET_NAME, successful_drafts)


async def generate_draft_for_lead(template, lead_data, subject, wave_id):
    """ Генерирует черновик письма. """
    lead_id = lead_data.get("lead_id")
    email = lead_data.get("email")
    company_name = lead_data.get("company_name", "Клиент")

    logger.info(f"📝 Генерируем черновик для lead_id={lead_id}...")

    prompt = f"""
    Шаблон письма:
    {template.text}

    Данные лида:
    {json.dumps(lead_data, ensure_ascii=False, indent=2)}

    Напиши персонализированное письмо.
    """

    for attempt in range(3):
        try:
            response = await send_to_model(prompt)
            break
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt + 1}: Ошибка генерации {lead_id}: {e}")
            if attempt == 2:
                logger.error(f"❌ Не удалось сгенерировать письмо для {lead_id}")
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