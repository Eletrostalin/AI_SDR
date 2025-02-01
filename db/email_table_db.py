import pandas as pd
from sqlalchemy import Table, MetaData, insert, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
import logging
from db.models import EmailTable

from db.db import engine, SessionLocal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def process_table_operations(df: pd.DataFrame, segment_table_name: str, chat_id: str, message, file_name) -> bool:
    """
    Открывает сессию, создаёт таблицу и сохраняет данные в БД.
    """
    db: Session = SessionLocal()
    try:
        from db.models import EmailTable, Company

        df.loc[:, 'table_name'] = file_name

        # Получение компании по chat_id
        company = db.query(Company).filter(Company.chat_id == chat_id).first()
        if not company:
            message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return False

        # Проверяем и создаем запись в EmailTable
        if not create_email_table_record(
                db,
                company_id=company.company_id,
                table_name=segment_table_name,
                description="Таблица сегментации email"
        ):
            message.reply("Ошибка при добавлении записи в сводную таблицу.")
            logger.error(f"Ошибка при создании записи для таблицы: {segment_table_name}")
            return False

        # Сохранение данных в БД
        if save_data_to_db(df.to_dict(orient="records"), segment_table_name, db):
            message.reply("Данные из таблицы успешно обработаны и сохранены.")
            logger.info(f"Данные успешно сохранены в таблицу: {segment_table_name}")
            return True
        else:
            message.reply("Ошибка при сохранении данных в базу.")
            logger.error(f"Ошибка при сохранении данных в таблицу: {segment_table_name}")
            return False
    finally:
        db.close()

def save_data_to_db(data: list, table_name: str, db: Session):
    """
    Сохраняет данные в динамическую таблицу сегментации email.

    :param data: Список записей для сохранения.
    :param table_name: Название таблицы для сохранения.
    :param db: Сессия базы данных.
    :return: True, если данные успешно сохранены, иначе False.
    """
    try:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=db.bind)

        stmt = insert(table).values(data)

        db.execute(stmt)
        db.commit()

        logger.info(f"Данные успешно сохранены в таблицу {table_name}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в таблицу {table_name}: {e}", exc_info=True)
        db.rollback()
        return False

def check_table_exists(db: Session, table_name: str) -> bool:
    """
    Проверяет существование таблицы в базе данных.

    :param db: Сессия базы данных.
    :param table_name: Имя таблицы.
    :return: True, если таблица существует, иначе False.
    """
    try:
        query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name
        )
        """)
        result = db.execute(query, {"table_name": table_name}).scalar()
        return result
    except Exception as e:
        logger.error(f"Ошибка при проверке таблицы {table_name}: {e}", exc_info=True)
        return False

def get_table_data(db: Session, table_name: str, limit: int = 1000) -> list:
    """
    Извлекает данные из указанной таблицы.

    :param db: Сессия базы данных.
    :param table_name: Имя таблицы.
    :param limit: Максимальное количество строк для извлечения.
    :return: Список строк таблицы в виде словарей.
    """
    try:
        # Оборачиваем имя таблицы в двойные кавычки для безопасности
        safe_table_name = f'"{table_name}"'
        query = text(f"SELECT * FROM {safe_table_name} LIMIT :limit")
        result = db.execute(query, {"limit": limit})

        # Используем .mappings() для преобразования строк в словари
        return [dict(row) for row in result.mappings()]
    except Exception as e:
        logger.error(f"Ошибка при извлечении данных из таблицы {table_name}: {e}", exc_info=True)
        return []

def create_email_table_record(db: Session, company_id: int, table_name: str, description: str = None) -> bool:
    """
    Создает или обновляет запись в сводной таблице email_tables.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :param table_name: Имя email таблицы.
    :param description: Описание email таблицы.
    :return: Успешность операции.
    """
    try:
        # Проверяем, существует ли уже запись с таким именем таблицы
        existing_record = db.query(EmailTable).filter(EmailTable.table_name == table_name).first()

        if existing_record:
            # Обновляем существующую запись
            logger.info(f"Обновление существующей записи для таблицы: {table_name}")
            existing_record.updated_at = func.now()
            if description:
                existing_record.description = description
        else:
            # Создаем новую запись
            logger.info(f"Создание новой записи для таблицы: {table_name}")
            new_email_table = EmailTable(
                company_id=company_id,
                table_name=table_name
            )
            db.add(new_email_table)

        # Сохраняем изменения
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении или обновлении записи в EmailTable: {e}", exc_info=True)
        db.rollback()
        return False