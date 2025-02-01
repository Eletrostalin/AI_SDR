from sqlalchemy import MetaData, Table, Column, Integer, String, DateTime, inspect
from sqlalchemy.exc import ProgrammingError
import logging

logger = logging.getLogger(__name__)

# Колонки, которые используются в динамических таблицах
DYNAMIC_EMAIL_TABLE_COLUMNS = [
    Column("table_name", String, nullable=True),
    Column("name", String, nullable=True),
    Column("region", String, nullable=True),
    Column("msp_registry", String, nullable=True),
    Column("director_name", String, nullable=True),
    Column("director_position", String, nullable=True),
    Column("phone_number", String, nullable=True),
    Column("email", String, nullable=True),
    Column("website", String, nullable=True),
    Column("primary_activity", String, nullable=True),
    Column("revenue", String, nullable=True),
    Column("employee_count", String, nullable=True),
    Column("branch_count", String, nullable=True)
]

def create_dynamic_email_table(engine, table_name: str) -> None:
    """
    Создаёт динамическую таблицу для сегментации email для конкретной компании.

    :param engine: SQLAlchemy engine для подключения к базе данных.
    :param table_name: Имя таблицы, которая должна быть создана.
    """
    try:
        metadata = MetaData()
        # Определение таблицы
        table = Table(
            table_name,
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            *DYNAMIC_EMAIL_TABLE_COLUMNS,
        )

        # Проверяем существование таблицы
        inspector = inspect(engine)
        if not inspector.has_table(table_name):
            metadata.create_all(engine, tables=[table])
            logger.info(f"Таблица '{table_name}' успешно создана.")
        else:
            logger.info(f"Таблица '{table_name}' уже существует.")
    except ProgrammingError as e:
        logger.error(f"Ошибка при создании таблицы '{table_name}': {e}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при создании таблицы '{table_name}': {e}")