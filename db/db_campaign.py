import json
from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db.models import Campaigns, ChatThread, Company
from logger import logger


async def create_campaign_and_thread(bot, db: Session, chat_id: int, campaign_data: dict) -> Campaigns:
    """
    Универсальная функция для создания/сохранения кампании.

    1. Всегда создает новую тему в Telegram.
    2. Проверяет существование `thread_id` в БД перед вставкой.
    3. Записывает данные (email_table_id, связи) в кампанию.

    Фильтры добавляются позже.

    :param bot: Объект бота.
    :param db: Сессия БД.
    :param chat_id: ID чата.
    :param campaign_data: Данные кампании (без фильтров).
    :return: Объект Campaigns.
    """
    try:
        company_id = campaign_data["company_id"]
        campaign_name = campaign_data["campaign_name"]
        email_table_id = campaign_data.get("email_table_id")

        # 🔹 ВСЕГДА создаем новую тему (игнорируем `thread_id` в `campaign_data`)
        topic = await bot.create_forum_topic(chat_id=chat_id, name=campaign_name)
        thread_id = topic.message_thread_id
        logger.info(f"✅ Создана новая тема: thread_id={thread_id}, chat_id={chat_id}")

        # 🔹 Проверяем, есть ли уже такая тема в БД (защита от дубликатов)
        existing_thread = db.query(ChatThread).filter_by(thread_id=thread_id).first()
        if existing_thread:
            logger.warning(f"⚠️ Тема с thread_id={thread_id} уже существует в БД! Используем существующую.")
        else:
            # ✅ Записываем новую тему в БД
            new_thread = ChatThread(chat_id=chat_id, thread_id=thread_id, thread_name=campaign_name)
            db.add(new_thread)
            db.commit()
            logger.info(f"✅ Новая тема успешно записана в БД: thread_id={thread_id}")

        # 🔹 Проверяем, существует ли уже кампания
        existing_campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if existing_campaign:
            logger.warning(f"⚠️ Кампания уже существует для темы thread_id={thread_id}. Обновляем данные.")
            existing_campaign.email_table_id = email_table_id
            db.commit()
            return existing_campaign

        # 🔹 Преобразуем даты
        start_date = (
            datetime.strptime(campaign_data.get("start_date"), "%d.%m.%Y").strftime("%Y-%m-%d")
            if campaign_data.get("start_date") else None
        )
        end_date = (
            datetime.strptime(campaign_data.get("end_date"), "%d.%m.%Y").strftime("%Y-%m-%d")
            if campaign_data.get("end_date") else None
        )

        # 🔹 Создаем кампанию
        new_campaign = Campaigns(
            company_id=company_id,
            thread_id=thread_id,  # 🔹 Всегда уникальный thread_id
            campaign_name=campaign_name,
            email_table_id=email_table_id,  # 🔹 Email-таблица
            status="active",
            status_for_user=True
        )

        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)

        logger.info(f"✅ Кампания успешно создана: id={new_campaign.campaign_id}, name={campaign_name}")
        return new_campaign

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при создании кампании: {e}", exc_info=True)
        raise


def get_campaigns_by_company_id(db: Session, company_id: int) -> list[Campaigns]:
    """
    Возвращает список всех кампаний для указанной компании.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :return: Список объектов Campaigns.
    """
    logger.debug(f"Запрос кампаний для компании company_id={company_id}")
    try:
        campaigns = db.query(Campaigns).filter_by(company_id=company_id).all()
        logger.info(f"Найдено {len(campaigns)} кампаний для company_id={company_id}")
        return campaigns
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении кампаний для company_id={company_id}: {e}", exc_info=True)
        return []


def get_campaign_by_thread_id(db: Session, thread_id: int) -> Campaigns | None:
    """
    Получает кампанию, связанную с данным thread_id.

    :param db: Сессия базы данных.
    :param thread_id: ID темы (thread_id).
    :return: Найденная кампания или None, если не найдена.
    """
    return db.query(Campaigns).filter_by(thread_id=thread_id).first()


import json
import re

def clean_string(value: str) -> str:
    """Удаляет экранирование Unicode из строки."""
    return value.encode('utf-8').decode('unicode_escape')

def update_campaign_filters(db: Session, campaign_id: int, filters: dict):
    """
    Обновляет фильтры в существующей кампании.

    :param db: Сессия базы данных.
    :param campaign_id: ID кампании.
    :param filters: Фильтры для обновления.
    """
    try:
        campaign = db.query(Campaigns).filter_by(campaign_id=campaign_id).first()
        if not campaign:
            logger.error(f"❌ Кампания с ID {campaign_id} не найдена.")
            return False

        # Приведение формата фильтров к корректному виду
        filters = normalize_filters(filters)

        # Логирование перед записью
        logger.info(f"📌 Записываем в БД: {filters}, тип: {type(filters)}")

        campaign.filters = filters  # Записываем как JSON
        db.commit()

        logger.info(f"✅ Успешно записали фильтры: {campaign.filters}")
        logger.info(f"✅ Фильтры успешно добавлены в кампанию ID {campaign_id}")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Ошибка при обновлении фильтров кампании ID {campaign_id}: {e}", exc_info=True)
        return False


def normalize_filters(filters: dict) -> dict:
    """
    Приводит фильтры к единому формату:
    - Строки преобразуются в списки, если ожидается список.
    - Сложные фильтры (диапазоны чисел) остаются без изменений.
    - Булевы значения остаются без изменений.

    :param filters: Фильтры в формате dict.
    :return: Преобразованные фильтры.
    """
    normalized_filters = {}

    for key, value in filters.items():
        if key == "region":  # Гарантируем, что region всегда будет списком
            if isinstance(value, str):
                normalized_filters[key] = [value]  # Превращаем строку в список
            elif isinstance(value, list):
                normalized_filters[key] = value  # Оставляем список как есть
            else:
                logger.warning(f"⚠️ Неожиданный формат region: {value}, тип: {type(value)}")
                normalized_filters[key] = value  # Логируем, но оставляем как есть

        elif isinstance(value, (int, bool, dict, list)):
            # Если значение уже в корректном формате, оставляем его
            normalized_filters[key] = value

        else:
            logger.warning(f"⚠️ Неожиданный формат фильтра {key}: {value}, тип: {type(value)}")
            normalized_filters[key] = value  # Логируем, но оставляем как есть

    return normalized_filters