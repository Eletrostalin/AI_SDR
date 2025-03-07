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