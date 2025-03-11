import asyncio
import json
import pandas as pd
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from config import DATABASE_URL
from db.models import Templates, Waves, Base
from logger import logger
from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model

# 🔹 Подключение к БД (замени на свои данные)
  # Можно поменять на PostgreSQL/MySQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🔹 ID Google Таблицы (если нужно сохранять)
SHEET_ID = "1YXv8CcjB_iOhDKAJZMkUV7BAmKE9x1kUrsN6cCWg2I8"
SHEET_NAME = "Черновики"

# 🔹 Данные волны (из скриншота)
TEST_WAVE = Waves(
    wave_id=20,
    content_plan_id=24,
    campaign_id=59,
    company_id=121,
    send_date="2025-03-10 00:00:00",
    subject="Первая волна"
)

# 🔹 Тестовый шаблон письма
TEST_TEMPLATE = Templates(
    campaign_id=59,
    template_content=(
        "Уважаемые Холодные лиды,\n\n"
        "Команда ООО Молодец сердечно приглашает вас на Новогодний корпоратив, "
        "который состоится 11 марта 2025 года в нашем офисе.\n\n"
        "Мы хотели бы отметить этот праздник вместе с вами, "
        "чтобы весело провести время, обсудить возможные сотрудничества и просто "
        "насладиться атмосферой праздника.\n\n"
        "Мы гарантируем вам отличное настроение, интересные разговоры и приятные впечатления. "
        "Пожалуйста, подтвердите свое участие до 5 марта.\n\n"
        "С наилучшими пожеланиями,\n"
        "Команда ООО Молодец\n\n"
        "P.S. Мы уверены, что вам понравится наше Новогоднее мероприятие!"
    ),
    subject="Приглашение на Новогодний корпоратив"
)

# 🔹 Тестовые лиды
TEST_LEADS = pd.DataFrame([
    {"lead_id": 1, "email": "test1@example.com", "company_name": "Компания 1"},
    {"lead_id": 2, "email": "test2@example.com", "company_name": "Компания 2"},
])


async def generate_draft_for_lead(template, lead_data, subject, wave_id):
    """
    Генерирует черновик письма для лида.
    """
    lead_id = lead_data.get("lead_id")
    email = lead_data.get("email")
    company_name = lead_data.get("company_name", "Клиент")

    logger.info(f"📝 Генерируем черновик для lead_id={lead_id}...")

    prompt = f"""
    Шаблон письма:
    {template.template_content}

    Данные лида:
    {json.dumps(lead_data, ensure_ascii=False, indent=2)}

    Задача: Напиши персонализированное письмо на основе шаблона и данных лида.
    """

    for attempt in range(3):
        try:
            response = await send_to_model(prompt)  # Вызов модели
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
        "subject": subject,
        "text": response.strip()
    }

    return draft


async def generate_drafts_for_wave(db, df, wave):
    """
    Генерация черновиков для тестовой волны.
    """
    logger.info(f"🚀 Начинаем генерацию черновиков для волны ID {wave.wave_id} (кол-во лидов: {len(df)})")

    # 1️⃣ Получаем тестовый шаблон письма
    template = TEST_TEMPLATE

    if not template:
        logger.error(f"❌ Нет шаблона для волны ID {wave.wave_id}. Пропускаем.")
        return

    email_subject = wave.subject
    batch_size = 50
    leads_batches = [df[i:i + batch_size] for i in range(0, len(df), batch_size)]

    for batch in leads_batches:
        tasks = []
        for _, lead in batch.iterrows():
            tasks.append(generate_draft_for_lead(template, lead, email_subject, wave.wave_id))

        results = await asyncio.gather(*tasks)

        successful_drafts = [res for res in results if res]

        # ✅ Вывод результатов в консоль вместо Google Sheets
        print("\n🔹 Сгенерированные черновики:")
        for draft in successful_drafts:
            print(json.dumps(draft, indent=4, ensure_ascii=False))

        # ✅ Можно сохранить в Google Sheets, если нужно
        # append_drafts_to_sheet(SHEET_ID, SHEET_NAME, successful_drafts)


async def run_test():
    async with SessionLocal() as db:
        await generate_drafts_for_wave(db, TEST_LEADS, TEST_WAVE)


if __name__ == "__main__":
    asyncio.run(run_test())