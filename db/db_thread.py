from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.models import ChatThread
from logger import logger
from db.db_campaign import create_campaign


def save_thread_to_db(db: Session, chat_id: str, thread_id: int, thread_name: str):
    """
    Сохраняет данные темы в базу данных.
    """
    try:
        new_thread = ChatThread(
            chat_id=chat_id,
            thread_id=thread_id,
            thread_name=thread_name,
        )
        db.add(new_thread)
        db.commit()
        logger.info(f"Тема сохранена в базу данных: chat_id={chat_id}, thread_id={thread_id}")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при сохранении темы в базу данных: {e}")
        db.rollback()
        raise ValueError("Ошибка при сохранении темы в базу данных.")

def save_campaign_to_db(db: Session, company_id: int, campaign_data: dict):
    """
    Сохраняет данные кампании в базу данных, включая сегменты.
    """
    logger.debug(f"Начало сохранения кампании в БД. company_id={company_id}, campaign_data={campaign_data}")
    try:
        # Создаем новую кампанию с данными
        new_campaign = create_campaign(
            db=db,
            company_id=company_id,
            campaign_name=campaign_data.get("campaign_name"),
            start_date=campaign_data.get("start_date"),
            end_date=campaign_data.get("end_date"),
            params=campaign_data.get("params", {}),
            segments=campaign_data.get("filters", {}),  # Сохраняем сегменты как JSON
            thread_id=campaign_data.get("thread_id"),
        )

        # Фиксируем изменения в базе данных
        db.commit()
        logger.info(
            f"Кампания сохранена в базу данных: id={new_campaign.campaign_id}, "
            f"name={new_campaign.campaign_name}, segments={new_campaign.segments}"
        )
        return new_campaign
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при сохранении кампании: {e}", exc_info=True)
        logger.debug(f"Данные, вызвавшие ошибку: company_id={company_id}, campaign_data={campaign_data}")
        db.rollback()
        raise ValueError("Ошибка при сохранении кампании в базу данных.")