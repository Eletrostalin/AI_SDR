from sqlalchemy.orm import Session
from db.models import Company, CompanyInfo


def get_company_by_chat_id(db: Session, chat_id: str) -> Company:
    """
    Возвращает объект компании по chat_id.
    """
    return db.query(Company).filter_by(chat_id=chat_id).first()


def get_company_by_telegram_id(db: Session, telegram_id: str) -> Company:
    """
    Возвращает объект компании по Telegram ID.
    """
    return db.query(Company).filter_by(telegram_id=telegram_id).first()


def create_company_if_not_exists(db: Session, telegram_id: str, chat_id: str) -> Company:
    """
    Создаёт новую запись о компании, если её не существует.
    """
    company = get_company_by_chat_id(db, chat_id)
    if not company:
        company = Company(
            telegram_id=telegram_id,
            chat_id=chat_id,
        )
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


def save_company_info(db: Session, company_id: int, details: dict) -> CompanyInfo:
    """
    Сохраняет или обновляет информацию о компании в таблице CompanyInfo.
    """
    company_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()
    if company_info:
        company_info.details = details
    else:
        company_info = CompanyInfo(
            company_id=company_id,
            details=details,
        )
        db.add(company_info)
    db.commit()
    db.refresh(company_info)
    return company_info