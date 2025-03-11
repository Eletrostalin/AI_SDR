import asyncio
import json
import pandas as pd
import schedule
from sqlalchemy.orm import Session
from datetime import datetime
from db.db import SessionLocal
from db.models import Waves
from handlers.draft_handlers.draft_handler import generate_drafts_for_wave
from logger import logger
from sqlalchemy.sql import text


def get_today_waves(db: Session):
    """ Получает волны, запланированные на сегодня. """
    today = datetime.utcnow().date()
    return db.query(Waves).filter(Waves.send_date == today).all()


def get_filtered_leads_for_wave(db: Session, wave_id: int) -> pd.DataFrame:
    """ Получает отфильтрованный список лидов для заданной волны. """
    try:
        wave_result = db.execute(
            text("SELECT campaign_id FROM waves WHERE wave_id = :wave_id"),
            {"wave_id": wave_id}
        ).fetchone()

        if not wave_result:
            logger.warning(f"⚠️ Волна с wave_id={wave_id} не найдена.")
            return pd.DataFrame()

        campaign_id = wave_result[0]

        campaign_result = db.execute(
            text("SELECT email_table_id, filters FROM campaigns WHERE campaign_id = :campaign_id"),
            {"campaign_id": campaign_id}
        ).fetchone()

        if not campaign_result:
            logger.warning(f"⚠️ Кампания с campaign_id={campaign_id} не найдена.")
            return pd.DataFrame()

        email_table_id, filters = campaign_result

        table_result = db.execute(
            text("SELECT table_name FROM email_tables WHERE email_table_id = :email_table_id"),
            {"email_table_id": email_table_id}
        ).fetchone()

        if not table_result:
            logger.warning(f"⚠️ Email-таблица с email_table_id={email_table_id} не найдена.")
            return pd.DataFrame()

        table_name = table_result[0]

        df = pd.read_sql(f"SELECT * FROM {table_name}", db.bind)

        if df.empty:
            logger.warning(f"⚠️ Таблица {table_name} пуста.")
            return pd.DataFrame()

        if filters:
            for key, value in filters.items():
                if key in df.columns:
                    if isinstance(value, list):
                        df = df[df[key].isin(value)]
                    elif isinstance(value, str):
                        df = df[df[key].str.contains(value, case=False, na=False)]
                    elif isinstance(value, dict):
                        for op, val in value.items():
                            if op == ">" and key in df.columns:
                                df = df[df[key] > val]
                            elif op == "<" and key in df.columns:
                                df = df[df[key] < val]

        logger.info(f"✅ Найдено {len(df)} лидов после фильтрации.")
        return df

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


async def scheduler_loop():
    """ Асинхронный цикл для запуска планировщика. """
    while True:
        await process_daily_waves()
        await asyncio.sleep(86400)  # Ожидание 24 часа (86400 секунд)


def start_scheduler():
    """ Функция теперь запускает асинхронную задачу вместо блокирующего цикла. """
    asyncio.create_task(scheduler_loop())  # Запуск в фоновом режиме
    logger.info("✅ Планировщик волн запущен в фоновом режиме.")