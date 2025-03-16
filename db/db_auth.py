from config import GOOGLE_SHEETS_POOL
from db.db import SessionLocal
from db.models import Company, User
from logger import logger
from sqlalchemy.orm import Session
from aiogram.types import User as TelegramUser



def create_or_get_company_and_user(db: Session, telegram_user: TelegramUser, chat_id: int):
    """
    Проверяет существование компании по chat_id.
    Если компании нет, создаёт новую компанию и пользователя.
    Если компания есть, создаёт только пользователя.
    """
    chat_id_str = str(chat_id)
    telegram_id_str = str(telegram_user.id)

    # Проверяем существование компании
    company = db.query(Company).filter_by(chat_id=chat_id_str).first()
    if not company:
        logger.info(f"Компания для чата {chat_id} не найдена. Создаём новую компанию.")
        # Получаем доступную Google-таблицу из конфигурации
        google_sheet_url = get_available_google_sheet()

        # Создаём новую компанию с привязкой Google-таблицы
        company = Company(
            chat_id=chat_id_str,
            telegram_id=telegram_id_str,
            google_sheet_url=google_sheet_url,
            google_sheet_name="Черновики"  # Название листа по умолчанию
        )

        db.add(company)
        db.commit()
        db.refresh(company)

    # Проверяем существование пользователя
    user = db.query(User).filter_by(telegram_id=telegram_id_str).first()
    if not user:
        logger.info(f"Пользователь с Telegram ID {telegram_id_str} не найден. Создаём нового пользователя.")
        # Создаём нового пользователя с именем из Telegram
        user = User(
            telegram_id=telegram_id_str,
            company_id=company.company_id,
            name=telegram_user.full_name or telegram_user.username or "Unknown"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def get_available_google_sheet():
    """
    Получает доступную Google таблицу из пула, проверяя, не используется ли она в таблице company.
    """
    db_session = SessionLocal()
    try:
        for sheet_url in GOOGLE_SHEETS_POOL.keys():
            if not is_google_sheet_used(db_session, sheet_url):  # Проверяем, используется ли таблица
                GOOGLE_SHEETS_POOL[sheet_url] = False
                return sheet_url
    finally:
        db_session.close()

    return None


def is_google_sheet_used(db_session: Session, sheet_url: str) -> bool:
    """
    Проверяет, используется ли Google таблица в таблице company.
    """
    return db_session.query(Company).filter(Company.google_sheet_url == sheet_url).first() is not None