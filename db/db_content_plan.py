import json

from sqlalchemy.orm import Session
from datetime import datetime

from db.db import SessionLocal
from db.models import Campaigns, ChatThread, ContentPlan, Waves
from logger import logger
from sqlalchemy.exc import SQLAlchemyError


def get_campaign_by_thread_id(db: Session, thread_id: int) -> Campaigns | None:
    """
    Возвращает кампанию по thread_id.
    """
    try:
        logger.debug(f"Получение кампании по thread_id={thread_id}")
        return db.query(Campaigns).filter_by(thread_id=thread_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении кампании: {e}", exc_info=True)
        return None


def create_content_plan(
        db: Session,
        company_id: int,
        chat_id: int,
        description: dict,
        wave_count: int
) -> ContentPlan | None:
    """
    Создает контент-план. Автоматически подтягивает последнюю активную кампанию по компании.
    """
    try:
        logger.debug(f"🔍 Поиск активной кампании для компании {company_id}")

        # Находим последнюю активную кампанию через ORM
        campaign = db.query(Campaigns)\
            .filter_by(company_id=company_id, status="active")\
            .order_by(Campaigns.created_at.desc())\
            .first()

        if not campaign:
            logger.error(f"❌ Не найдено активных кампаний для компании {company_id}")
            return None

        campaign_id = campaign.campaign_id
        logger.info(f"📌 Используем campaign_id={campaign_id} для создания контент-плана.")

        # Логирование входных данных
        logger.debug(f"📋 Входные данные для контент-плана: chat_id={chat_id}, wave_count={wave_count}")
        logger.debug(f"📋 Описание контент-плана: {description}")

        # Преобразуем описание в JSON-строку
        description_json = json.dumps(description, ensure_ascii=False)

        content_plan = ContentPlan(
            company_id=company_id,
            telegram_id=str(chat_id),
            description=description_json,
            wave_count=wave_count,
            campaign_id=campaign_id
        )
        db.add(content_plan)
        db.commit()
        db.refresh(content_plan)

        logger.info(f"✅ Контентный план создан: id={content_plan.content_plan_id}")
        return content_plan
    except SQLAlchemyError as e:
        logger.error(f"❌ Ошибка при создании контентного плана: {e}", exc_info=True)
        db.rollback()
        return None


def add_wave(
        db: Session,
        content_plan_id: int,
        company_id: int,
        campaign_id: int,
        send_date: str,
        subject: str
) -> Waves | None:
    """
    Добавляет волну в контентный план.
    """
    try:
        logger.debug(f"🔍 Добавление волны: content_plan_id={content_plan_id}, campaign_id={campaign_id}")
        logger.debug(f"📅 Дата отправки: {send_date}, 📢 Тема: {subject}")

        # Преобразуем дату в объект datetime
        send_date_parsed = datetime.strptime(send_date, "%Y-%m-%d").date()

        if not subject.strip():
            raise ValueError("Поле 'subject' не может быть пустым.")

        new_wave = Waves(
            content_plan_id=content_plan_id,
            company_id=company_id,
            campaign_id=campaign_id,
            send_date=send_date_parsed,
            subject=subject,
        )
        db.add(new_wave)
        db.commit()
        db.refresh(new_wave)

        logger.info(f"✅ Волна добавлена: id={new_wave.wave_id}, subject={subject}")
        return new_wave
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"❌ Ошибка при добавлении волны: {e}", exc_info=True)
        db.rollback()
        return None

def get_content_plans_by_campaign_id(db: Session, campaign_id: int):
    """
    Получает список контентных планов для заданной кампании.

    :param db: Сессия базы данных SQLAlchemy.
    :param campaign_id: ID кампании.
    :return: Список объектов ContentPlan.
    """
    try:
        logger.debug(f"Получение контентных планов для campaign_id={campaign_id}")
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign_id).all()
        if not content_plans:
            logger.info(f"Для campaign_id={campaign_id} не найдено контентных планов.")
        return content_plans
    except Exception as e:
        logger.error(f"Ошибка при получении контентных планов для campaign_id={campaign_id}: {e}", exc_info=True)
        return []



