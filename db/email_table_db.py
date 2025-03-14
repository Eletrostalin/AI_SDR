import pandas as pd
from sqlalchemy import Table, MetaData, insert, func
from sqlalchemy.sql import text
import logging
from db.models import EmailTable, Campaigns

from db.db import engine, SessionLocal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def process_table_operations(df: pd.DataFrame, file_name: str, chat_id: str, message, table_name) -> bool:
    """
    Открывает сессию, создаёт таблицу и сохраняет данные в БД.
    """
    db: Session = SessionLocal()
    try:
        from db.models import EmailTable, Company

        # ✅ Добавляем колонку `file_name`, если её ещё нет
        if "file_name" not in df.columns:
            df["file_name"] = file_name

        # Получаем компанию по chat_id
        company = db.query(Company).filter(Company.chat_id == chat_id).first()
        if not company:
            message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return False

        # ✅ Создаём запись в EmailTable с `file_name`
        if not create_email_table_record(
                db,
                company_id=company.company_id,
                table_name=table_name,  # Используем `table_name`, а не file_name
                description=f"Таблица сегментации email ({file_name})"
        ):
            message.reply("Ошибка при добавлении записи в сводную таблицу.")
            logger.error(f"Ошибка при создании записи для таблицы: {table_name}")
            return False

        # ✅ Сохранение данных в БД (теперь `file_name` передаётся в `df`)
        if save_data_to_db(df.to_dict(orient="records"), table_name, db):
            message.reply(f"✅ Данные из {file_name} успешно обработаны и сохранены.")
            return True
        else:
            message.reply(f"❌ Ошибка при сохранении данных из {file_name}.")
            logger.error(f"Ошибка при сохранении данных в таблицу: {table_name}")
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
        if not data:
            logger.warning(f"⚠️ Пустой список данных передан для сохранения в {table_name}. Операция пропущена.")
            return False

        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=db.bind)

        logger.debug(f"📌 Подготовка данных для вставки в {table_name}: {data[:5]} (показаны первые 5 записей)")
        logger.debug(f"📌 Выполняется SQL-запрос на вставку {len(data)} записей в {table_name}")

        stmt = insert(table).values(data)
        db.execute(stmt)
        db.commit()

        logger.info(f"✅ Данные успешно сохранены в таблицу {table_name}.")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении данных в {table_name}: {e}", exc_info=True)
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

def get_table_by_campaign(campaign: Campaigns) -> str | None:
    """Определяет таблицу, связанную с кампанией"""
    db = SessionLocal()
    try:
        table = db.query(EmailTable).filter_by(company_id=campaign.company_id).first()
        return table.table_name if table else None
    finally:
        db.close()