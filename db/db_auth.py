from sqlalchemy.orm import Session
from db.models import User, Company
from sqlalchemy.exc import IntegrityError


def create_user_and_company(db: Session, telegram_id: int, chat_id: int) -> User:
    """
    Создаёт пользователя и связанную с ним компанию, если они не существуют.
    """
    telegram_id_str = str(telegram_id)
    chat_id_str = str(chat_id)

    try:
        # Проверяем существование компании
        company = db.query(Company).filter_by(chat_id=chat_id_str).first()
        if not company:
            # Если компании нет, создаём новую
            company = Company(
                chat_id=chat_id_str,
                telegram_id=telegram_id_str,
            )
            db.add(company)
            db.commit()
            db.refresh(company)

        # Проверяем существование пользователя
        user = db.query(User).filter_by(telegram_id=telegram_id_str).first()
        if not user:
            # Если пользователя нет, создаём его
            user = User(
                telegram_id=telegram_id_str,
                company_id=company.company_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
    except IntegrityError as e:
        db.rollback()
        raise e