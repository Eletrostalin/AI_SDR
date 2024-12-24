from sqlalchemy.orm import Session
from datetime import datetime
from db.models import Campaigns, ChatThread, ContentPlan, Waves
from logger import logger


def get_chat_thread(db: Session, chat_id: int, thread_id: int):
    """
    Возвращает тему чата по chat_id и thread_id.
    """
    chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
    if not chat_thread:
        logger.error(f"Тема с chat_id={chat_id} и thread_id={thread_id} не найдена.")
    return chat_thread


def get_campaign_by_thread_id(db: Session, thread_id: int):
    """
    Возвращает кампанию по thread_id.
    """
    campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
    if not campaign:
        logger.error(f"Кампания с thread_id={thread_id} не найдена.")
    return campaign


def create_content_plan(db: Session, company_id: int, chat_id: int, description: str, wave_count: int, campaign_id: int):
    """
    Создает запись контентного плана.
    """
    content_plan = ContentPlan(
        company_id=company_id,
        telegram_id=str(chat_id),
        description=description,
        wave_count=wave_count,
        campaign_id=campaign_id
    )
    db.add(content_plan)
    db.commit()
    db.refresh(content_plan)
    logger.info(f"Контентный план создан: id={content_plan.content_plan_id}, description={description}")
    return content_plan


def add_wave(db: Session, content_plan_id: int, company_id: int, campaign_id: int, wave: dict):
    """
    Добавляет волну к контентному плану.
    """
    send_datetime = datetime.combine(
        datetime.strptime(wave["send_date"], "%Y-%m-%d").date(),
        datetime.strptime(wave["send_time"], "%H:%M:%S").time()
    )
    new_wave = Waves(
        content_plan_id=content_plan_id,
        company_id=company_id,
        campaign_id=campaign_id,
        send_date=send_datetime.date(),
        send_time=send_datetime.time(),
        subject=wave["subject"]
    )
    db.add(new_wave)
    logger.debug(f"Добавлена волна: {new_wave}")