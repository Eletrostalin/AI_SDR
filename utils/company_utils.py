from sqlalchemy.orm import Session
from db.models import Company, CompanyInfo

def get_company_by_telegram_id(db: Session, telegram_id: str) -> Company:
    """
    Возвращает объект компании по Telegram ID.
    """
    return db.query(Company).filter_by(telegram_id=telegram_id).first()

def get_company_info(db: Session, company_id: int) -> CompanyInfo:
    """
    Возвращает информацию о компании по её ID.
    """
    return db.query(CompanyInfo).filter_by(company_id=company_id).first()

def create_company(db: Session, telegram_id: str, chat_id: str) -> Company:
    """
    Создаёт новую запись о компании.
    """
    new_company = Company(
        telegram_id=telegram_id,
        chat_id=chat_id,
    )
    db.add(new_company)
    db.commit()
    db.refresh(new_company)
    return new_company

def update_company_status(db: Session, company_id: int, status: str) -> None:
    """
    Обновляет статус компании.
    """
    company = db.query(Company).filter_by(company_id=company_id).first()
    if company:
        company.status = status
        db.commit()

def save_company_info(db: Session, company_id: int, details: dict) -> CompanyInfo:
    """
    Сохраняет или обновляет информацию о компании.
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