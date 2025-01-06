<<<<<<< HEAD
from sqlalchemy import Table, MetaData, Column, Integer, String
from sqlalchemy.orm import Session
import logging

from db.models import SegmentSummary

logger = logging.getLogger(__name__)

def create_segment_table(table_name: str, filters: dict, db: Session):
    """
    Создает новую таблицу для сегмента в базе данных.

    :param table_name: Имя новой таблицы.
    :param filters: Список колонок для таблицы.
    :param db: Сессия базы данных.
    """
    try:
        metadata = MetaData()  # Создаем объект MetaData без параметра bind

        # Формируем базовые колонки
        columns = [
            Column("id", Integer, primary_key=True, autoincrement=True)
        ]

        # Добавляем колонки на основе подтвержденных фильтров
        for column in filters:
            columns.append(Column(column, String))

        # Создаем таблицу
        table = Table(table_name, metadata, *columns)

        # Привязываем metadata к движку из сессии базы данных
        metadata.create_all(bind=db.get_bind())

        logger.info(f"Таблица '{table_name}' успешно создана с колонками: {', '.join(filters)}.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы '{table_name}': {e}", exc_info=True)
        raise

def add_segment_summary(db: Session, company_id: int, table_name: str, description: str, filters: dict):
    """
    Добавляет запись о сегменте в сводную таблицу.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :param table_name: Имя таблицы сегмента.
    :param description: Описание сегмента.
    :param filters: Параметры сегментации (фильтры).
    """
    try:
        # Создаем запись о сегменте
        new_segment = SegmentSummary(
            company_id=company_id,
            segment_table_name=table_name,
            description=description,
            params=filters
        )

        # Добавляем запись в базу
        db.add(new_segment)
        db.commit()

        logger.info(f"Сегмент '{table_name}' успешно добавлен в сводную таблицу.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении записи о сегменте '{table_name}': {e}", exc_info=True)
        db.rollback()
        raise

def get_segments_by_company_id(db: Session, company_id: int):
    """
    Извлекает все сегменты, связанные с данной компанией.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :return: Список объектов SegmentSummary.
    """
    return db.query(SegmentSummary).filter(SegmentSummary.company_id == company_id).all()
=======
# from sqlalchemy import Table, MetaData, Column, Integer, String
# from sqlalchemy.orm import Session
# import logging
#
# from db.models import SegmentSummary
#
# logger = logging.getLogger(__name__)
#
# def create_segment_table(table_name: str, filters: dict, db: Session):
#     """
#     Создает новую таблицу для сегмента в базе данных.
#
#     :param table_name: Имя новой таблицы.
#     :param filters: Список колонок для таблицы.
#     :param db: Сессия базы данных.
#     """
#     try:
#         metadata = MetaData()  # Создаем объект MetaData без параметра bind
#
#         # Формируем базовые колонки
#         columns = [
#             Column("id", Integer, primary_key=True, autoincrement=True)
#         ]
#
#         # Добавляем колонки на основе подтвержденных фильтров
#         for column in filters:
#             columns.append(Column(column, String))
#
#         # Создаем таблицу
#         table = Table(table_name, metadata, *columns)
#
#         # Привязываем metadata к движку из сессии базы данных
#         metadata.create_all(bind=db.get_bind())
#
#         logger.info(f"Таблица '{table_name}' успешно создана с колонками: {', '.join(filters)}.")
#     except Exception as e:
#         logger.error(f"Ошибка при создании таблицы '{table_name}': {e}", exc_info=True)
#         raise
#
# def add_segment_summary(db: Session, company_id: int, table_name: str, description: str, filters: dict):
#     """
#     Добавляет запись о сегменте в сводную таблицу.
#
#     :param db: Сессия базы данных.
#     :param company_id: ID компании.
#     :param table_name: Имя таблицы сегмента.
#     :param description: Описание сегмента.
#     :param filters: Параметры сегментации (фильтры).
#     """
#     try:
#         # Создаем запись о сегменте
#         new_segment = SegmentSummary(
#             company_id=company_id,
#             segment_table_name=table_name,
#             description=description,
#             params=filters
#         )
#
#         # Добавляем запись в базу
#         db.add(new_segment)
#         db.commit()
#
#         logger.info(f"Сегмент '{table_name}' успешно добавлен в сводную таблицу.")
#     except Exception as e:
#         logger.error(f"Ошибка при добавлении записи о сегменте '{table_name}': {e}", exc_info=True)
#         db.rollback()
#         raise
#
# def get_segments_by_company_id(db: Session, company_id: int):
#     """
#     Извлекает все сегменты, связанные с данной компанией.
#
#     :param db: Сессия базы данных.
#     :param company_id: ID компании.
#     :return: Список объектов SegmentSummary.
#     """
#     return db.query(SegmentSummary).filter(SegmentSummary.company_id == company_id).all()
>>>>>>> try_langchain
