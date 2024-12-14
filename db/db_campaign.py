from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from logger import logger
from db.models import Campaigns


def create_campaign(db: Session, company_id: int, campaign_name: str, start_date: str, end_date: str, params: dict) -> Campaigns:
    """
    Создает новую кампанию в базе данных.
    """
    logger.debug(f"Создание кампании: company_id={company_id}, campaign_name={campaign_name}, start_date={start_date}, end_date={end_date}, params={params}")

    # Преобразуем даты в формат YYYY-MM-DD
    try:
        start_date = datetime.strptime(start_date, "%d.%m.%Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError as e:
        logger.error(f"Некорректный формат даты: {e}")
        raise ValueError("Неверный формат даты. Используйте формат ДД.ММ.ГГГГ.")

    new_campaign = Campaigns(
        company_id=company_id,
        campaign_name=campaign_name,
        start_date=start_date,
        end_date=end_date,
        params=params
    )
    db.add(new_campaign)
    try:
        db.commit()
        db.refresh(new_campaign)
        logger.info(f"Кампания успешно создана: id={new_campaign.campaign_id}, name={new_campaign.campaign_name}")
        return new_campaign
    except IntegrityError as e:
        logger.error(f"Ошибка IntegrityError при создании кампании: {e}")
        db.rollback()
        raise ValueError("Ошибка при создании кампании. Возможно, такая кампания уже существует.")
    except Exception as e:
        logger.error(f"Ошибка при создании кампании: {e}", exc_info=True)
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