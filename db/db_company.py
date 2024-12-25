from sqlalchemy.orm import Session
from db.models import Company, CompanyInfo
from logger import logger


def get_company_by_chat_id(db: Session, chat_id: str) -> Company:
    """
    Возвращает объект компании по chat_id.
    """
    result = db.query(Company).filter_by(chat_id=chat_id).first()
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


def update_company_info(db: Session, company_id: int, new_details: dict) -> None:
    """
    Обновляет информацию о компании в таблице CompanyInfo.

    :param db: Сессия базы данных.
    :param company_id: ID компании для обновления.
    :param new_details: Новый JSON-объект с деталями компании.
    """
    company_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()
    if company_info:
        company_info.details = new_details
        db.commit()
        db.refresh(company_info)
    else:
        raise ValueError(f"Информация о компании с ID {company_id} не найдена.")


def validate_and_merge_company_info(
    db: Session, company_id: int, fields_to_add: dict
) -> dict:
    """
    Проверяет существующие данные компании, ищет пересечения ключей, объединяет новые данные.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :param fields_to_add: Данные для добавления.
    :return: Новые данные, объединенные с существующими, или выбрасывает исключение.
    """
    existing_data = get_company_info_by_company_id(db, company_id) or {}
    overlapping_keys = set(fields_to_add.keys()) & set(existing_data.keys())

    if overlapping_keys:
        raise ValueError(
            f"Поля {', '.join(overlapping_keys)} уже существуют. Обновление невозможно."
        )

    # Объединяем данные
    return {**existing_data, **fields_to_add}


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

