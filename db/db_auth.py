from db.models import Company, User
from logger import logger
from sqlalchemy.orm import Session



def create_or_get_company_and_user(db: Session, telegram_id: int, chat_id: int):
    """
    Проверяет существование компании по chat_id.
    Если компании нет, создаёт новую компанию и пользователя.
    Если компания есть, создаёт только пользователя.
    """
    chat_id_str = str(chat_id)
    telegram_id_str = str(telegram_id)

    # Проверяем существование компании
    company = db.query(Company).filter_by(chat_id=chat_id_str).first()
    if not company:
        logger.info(f"Компания для чата {chat_id} не найдена. Создаём новую компанию.")
        # Создаём новую компанию
        company = Company(chat_id=chat_id_str, telegram_id=telegram_id_str)
        db.add(company)
        db.commit()
        db.refresh(company)

    # Проверяем существование пользователя
    user = db.query(User).filter_by(telegram_id=telegram_id_str).first()
    if not user:
        logger.info(f"Пользователь с Telegram ID {telegram_id} не найден. Создаём нового пользователя.")
        # Создаём нового пользователя, связанного с компанией
        user = User(telegram_id=telegram_id_str, company_id=company.company_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user