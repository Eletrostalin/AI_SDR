import asyncio
import json
import pandas as pd
import schedule
from sqlalchemy.orm import Session
from datetime import datetime
from db.db import SessionLocal
from db.models import Waves, EmailTable, Campaigns
from handlers.draft_handlers.draft_handler import generate_drafts_for_wave
from logger import logger
from sqlalchemy.exc import SQLAlchemyError



def get_today_waves(db: Session):
    """ Получает волны, запланированные на сегодня. """
    today = datetime.utcnow().date()
    return db.query(Waves).filter(Waves.send_date == today).all()


def get_filtered_leads_for_wave(db: Session, wave_id: int) -> pd.DataFrame:
    """ Получает отфильтрованный список лидов для заданной волны. """
    try:
        wave = db.query(Waves).filter(Waves.wave_id == wave_id).first()
        if not wave:
            logger.warning(f"⚠️ Волна с wave_id={wave_id} не найдена.")
            return pd.DataFrame()

        campaign = db.query(Campaigns).filter(Campaigns.campaign_id == wave.campaign_id).first()
        if not campaign:
            logger.warning(f"⚠️ Кампания с campaign_id={wave.campaign_id} не найдена.")
            return pd.DataFrame()

        email_table = db.query(EmailTable).filter(EmailTable.email_table_id == campaign.email_table_id).first()
        if not email_table:
            logger.warning(f"⚠️ Email-таблица с email_table_id={campaign.email_table_id} не найдена.")
            return pd.DataFrame()

        filters = {}
        if isinstance(campaign.filters, str):
            try:
                filters = json.loads(campaign.filters)
            except json.JSONDecodeError:
                logger.error(f"❌ Ошибка декодирования JSON-фильтров: {campaign.filters}")

        logger.info(f"🔍 Загруженные фильтры: {filters}")

        # Загружаем данные из таблицы
        df = pd.read_sql(f"SELECT * FROM {email_table.table_name}", db.bind)

        if df.empty:
            logger.warning(f"⚠️ Таблица {email_table.table_name} пуста.")
            return pd.DataFrame()

        # Применяем фильтры
        for key, value in filters.items():
            if key in df.columns:
                if isinstance(value, list):
                    df = df[df[key].isin(value)]
                elif isinstance(value, str):
                    values = [v.strip() for v in value.split(",")]
                    df = df[df[key].isin(values)]
                elif isinstance(value, dict):
                    for op, val in value.items():
                        if op == ">" and key in df.columns:
                            df = df[df[key] > val]
                        elif op == "<" and key in df.columns:
                            df = df[df[key] < val]

        logger.info(f"✅ Найдено {len(df)} лидов после фильтрации.")
        return df

    except SQLAlchemyError as e:
        logger.error(f"❌ Ошибка базы данных: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Ошибка при получении лидов для волны: {e}", exc_info=True)

    return pd.DataFrame()


async def process_daily_waves():
    """ Проверяет волны и запускает генерацию черновиков. """
    logger.info("🔄 Проверка запланированных волн на сегодня...")

    with SessionLocal() as db:
        waves = get_today_waves(db)
        if not waves:
            logger.info("📭 На сегодня нет запланированных волн.")
            return

        for wave in waves:
            df = get_filtered_leads_for_wave(db, wave.wave_id)
            if df.empty:
                logger.warning(f"⚠️ Нет лидов для волны ID {wave.wave_id}")
                continue

            await generate_drafts_for_wave(db, df, wave)


def schedule_job():
    """ Запускает запланированную задачу каждый день в 00:00 UTC. """
    schedule.every().day.at("00:00").do(lambda: asyncio.create_task(process_daily_waves()))
    logger.info("🕛 Запуск джобы запланирован на 00:00 UTC.")


async def scheduler_loop():
    """ Асинхронный цикл для работы schedule. """
    schedule_job()
    while True:
        schedule.run_pending()
        await asyncio.sleep(60)  # Проверка раз в минуту


def start_scheduler():
    """ Запускает планировщик в фоновом режиме. """
    asyncio.create_task(scheduler_loop())  # Запуск в фоне
    logger.info("✅ Планировщик волн запущен в фоновом режиме и срабатывает каждый день в 00:00 UTC.")