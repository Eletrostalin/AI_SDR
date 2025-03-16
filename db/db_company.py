from datetime import datetime

from sqlalchemy.orm import Session

from config import GOOGLE_SHEETS_POOL
from db.db import SessionLocal
from db.models import Company, CompanyInfo, Campaigns
from logger import logger


def get_company_by_chat_id(db: Session, chat_id: str) -> Company:
    """
    Возвращает объект компании по chat_id.
    """
    result = db.query(Company).filter_by(chat_id=str(chat_id)).first()
    print(result)
    return result


def get_company_by_telegram_id(db: Session, telegram_id: str) -> Company:
    """
    Возвращает объект компании по Telegram ID.
    """
    return db.query(Company).filter_by(telegram_id=telegram_id).first()


def get_company_info_by_company_id(db: Session, company_id: int) -> dict:
    """
    Возвращает информацию о компании из таблицы CompanyInfo по company_id.
    """
    company_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()
    if not company_info:
        return None

    # Преобразуем объект CompanyInfo в словарь без полей created_at и updated_at
    return {
        "company_name": company_info.company_name,
        "industry": company_info.industry,
        "region": company_info.region,
        "contact_email": company_info.contact_email,
        "contact_phone": company_info.contact_phone,
        "additional_info": company_info.additional_info,
    }


def get_company_by_campaign(campaign: Campaigns):
    """Получает компанию, связанную с кампанией."""
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(company_id=campaign.company_id).first()
        return company
    finally:
        db.close()



def save_company_info(company_id: int, brief_data: dict):
    """
    Сохраняет данные компании в базу данных (обновляет или создает новую запись).
    """
    db: Session = SessionLocal()
    try:
        existing_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()

        if existing_info:
            logger.info(f"Обновляем данные компании ID: {company_id}")
            for key, value in brief_data.items():
                setattr(existing_info, key, value)
            existing_info.updated_at = datetime.utcnow()
        else:
            logger.info(f"Создаем новую запись для компании ID: {company_id}")
            new_info = CompanyInfo(**brief_data, company_id=company_id, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
            db.add(new_info)

        db.commit()
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных компании: {e}", exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()

    return True


def delete_additional_info(db: Session, company_id: int):
    """
    Очищает содержимое колонки `additional_info` для указанной компании.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    """
    try:
        company_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()

        if not company_info:
            raise ValueError(f"Информация о компании с ID {company_id} не найдена.")

        # Удаляем содержимое колонки
        company_info.additional_info = None
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при удалении содержимого additional_info: {e}", exc_info=True)
        raise


def get_available_google_sheet():
    """
    Возвращает первую доступную Google-таблицу и помечает её как использованную.
    """
    for sheet_url, available in GOOGLE_SHEETS_POOL.items():
        if available:
            GOOGLE_SHEETS_POOL[sheet_url] = False  # Блокируем использование этой ссылки
            return sheet_url
    return None  # Если все ссылки заняты

