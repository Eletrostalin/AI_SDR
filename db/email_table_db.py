from sqlalchemy import Table, MetaData, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


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