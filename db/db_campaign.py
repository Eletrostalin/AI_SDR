from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db.db import SessionLocal
from logger import logger
from db.models import Campaigns, ChatThread, Waves


def create_campaign(
    db: Session,
    company_id: int,
    campaign_name: str,
    start_date: str,
    end_date: str,
    params: dict,
    segments: dict,
    thread_id: int,
) -> Campaigns:
    """
    Создает новую кампанию в базе данных.
    """
    logger.debug(
        f"Создание кампании: company_id={company_id}, campaign_name={campaign_name}, "
        f"start_date={start_date}, end_date={end_date}, params={params}, segments={segments}, thread_id={thread_id}"
    )

    # Преобразование дат в формат YYYY-MM-DD
    try:
        start_date = datetime.strptime(start_date, "%d.%m.%Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Некорректный формат даты: {e}")
        raise ValueError("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.")

    # Проверка существования thread_id
    chat_thread = db.query(ChatThread).filter_by(thread_id=thread_id).first()
    if not chat_thread:
        logger.error(f"Тема с thread_id={thread_id} не найдена. Невозможно создать кампанию.")
        raise ValueError("Ошибка: Тема с указанным thread_id не существует.")

    # Создание кампании
    try:
        new_campaign = Campaigns(
            company_id=company_id,
            campaign_name=campaign_name,
            start_date=start_date,
            end_date=end_date,
            params=params,
            segments=segments,  # Сохраняем сегменты
            thread_id=thread_id,
        )
        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)
        logger.info(
            f"Кампания успешно создана: id={new_campaign.campaign_id}, "
            f"name={new_campaign.campaign_name}, segments={segments}, thread_id={thread_id}"
        )
        return new_campaign
    except IntegrityError as e:
        logger.error(f"Ошибка IntegrityError при создании кампании: {e}")
        db.rollback()
        raise ValueError("Ошибка при создании кампании. Возможно, такая кампания уже существует.")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemyError при создании кампании: {e}", exc_info=True)
        db.rollback()
        raise


def get_campaign_by_id(db: Session, campaign_id: int) -> Campaigns:
    """
    Получает кампанию по ее ID.

    :param db: Сессия базы данных.
    :param campaign_id: ID кампании.
    :return: Найденная кампания или None.
    """
    return db.query(Campaigns).filter_by(campaign_id=campaign_id).first()

def get_campaigns_by_company_id(db: Session, company_id: int) -> list[Campaigns]:
    """
    Возвращает список кампаний для указанной компании.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :return: Список кампаний.
    """
    return db.query(Campaigns).filter_by(company_id=company_id).all()

def update_campaign_status(db: Session, campaign_id: int, status: str) -> None:
    """
    Обновляет статус кампании.

    :param db: Сессия базы данных.
    :param campaign_id: ID кампании.
    :param status: Новый статус.
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if campaign:
        campaign.status = status
        db.commit()
    else:
        raise ValueError(f"Кампания с ID {campaign_id} не найдена.")

def delete_campaign(db: Session, campaign_id: int) -> None:
    """
    Удаляет кампанию по ее ID.

    :param db: Сессия базы данных.
    :param campaign_id: ID кампании.
    """
    campaign = get_campaign_by_id(db, campaign_id)
    if campaign:
        db.delete(campaign)
        db.commit()
    else:
        raise ValueError(f"Кампания с ID {campaign_id} не найдена.")

def get_campaign_by_thread_id(thread_id: int) -> Campaigns:
    """Получает кампанию, связанную с данным thread_id"""
    db = SessionLocal()
    try:
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        return campaign
    finally:
        db.close()

def get_campaign_by_wave(wave: Waves) -> Campaigns | None:
    """Получает кампанию, связанную с волной"""
    return wave.campaign if wave else None