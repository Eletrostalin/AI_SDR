from sqlalchemy import MetaData, Table, Column, Integer, String, inspect
from sqlalchemy.exc import ProgrammingError
import logging

logger = logging.getLogger(__name__)

# Определение динамических колонок в виде списка кортежей (имя, тип)
DYNAMIC_EMAIL_TABLE_COLUMNS = [
    ("file_name", String),
    ("name", String),
    ("region", String),
    ("msp_registry", String),
    ("director_name", String),
    ("director_position", String),
    ("phone_number", String),
    ("email", String),
    ("website", String),
    ("primary_activity", String),
    ("revenue", String),
    ("employee_count", String),
    ("branch_count", String)
]


def create_dynamic_email_table(engine, table_name: str) -> None:
    """
    Создаёт динамическую таблицу для сегментации email для конкретной компании.

    :param engine: SQLAlchemy engine для подключения к базе данных.
    :param table_name: Имя таблицы, которая должна быть создана.
    """
    try:
        metadata = MetaData(bind=engine)  # Используем привязанный metadata
        inspector = inspect(engine)

        existing_tables = inspector.get_table_names()
        logger.debug(f"📋 Существующие таблицы: {existing_tables}")

        if table_name in existing_tables:
            logger.warning(f"⚠️ Таблица '{table_name}' уже существует. Пропускаем создание.")
            return

        logger.debug(f"📌 Генерируем колонки для таблицы '{table_name}'")

        # Создаём новые объекты `Column()` для каждой таблицы, чтобы избежать конфликта
        dynamic_columns = [Column("id", Integer, primary_key=True, autoincrement=True)] + [
            Column(name, col_type, nullable=True) for name, col_type in DYNAMIC_EMAIL_TABLE_COLUMNS
        ]

        table = Table(table_name, metadata, *dynamic_columns)
        logger.debug(f"📌 Создаём таблицу '{table_name}' с колонками: {[col.name for col in table.columns]}")

        metadata.create_all(engine, tables=[table])

        logger.info(f"✅ Таблица '{table_name}' успешно создана.")
    except ProgrammingError as e:
        logger.error(f"❌ Ошибка при создании таблицы '{table_name}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка при создании таблицы '{table_name}': {e}", exc_info=True)