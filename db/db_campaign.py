from datetime import datetime
from aiogram import Bot
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db.models import Campaigns, ChatThread
from db.db_thread import save_thread_to_db, get_thread_by_chat_id
from db.db_company import get_company_by_chat_id
from logger import logger


async def create_campaign_and_thread(
    bot: Bot,
    db: Session,
    chat_id: int,
    campaign_name: str,
) -> Campaigns:
    """
    Создаёт новую тему (thread) в чате и кампанию в базе данных.

    :param bot: Экземпляр бота для создания темы в Telegram.
    :param db: Сессия БД.
    :param chat_id: ID чата.
    :param campaign_name: Название кампании.
    :return: Объект Campaigns.
    """
    logger.debug(f"Создание темы и кампании: chat_id={chat_id}, campaign_name={campaign_name}")

    # Получаем компанию по chat_id
    company = get_company_by_chat_id(db, str(chat_id))  # chat_id приводим к строке, если нужно
    if not company:
        logger.error(f"Компания для chat_id={chat_id} не найдена.")
        raise ValueError("Ошибка: Компания не найдена.")

    # Проверяем, существует ли уже тема в БД
    thread = get_thread_by_chat_id(db, chat_id)
    if thread:
        thread_id = thread.thread_id
        logger.debug(f"Используем существующую тему с thread_id={thread_id}")
    else:
        # Создаём новую тему в Telegram
        try:
            topic = await bot.create_forum_topic(chat_id=chat_id, name=campaign_name)
            thread_id = topic.message_thread_id  # Telegram API возвращает ID темы
            save_thread_to_db(db, chat_id, thread_id, thread_name=campaign_name)
            logger.info(f"Создана новая тема: thread_id={thread_id}, chat_id={chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при создании темы в Telegram: {e}", exc_info=True)
            raise ValueError("Ошибка при создании темы чата в Telegram.")

    # Создаем кампанию
    new_campaign = Campaigns(
        company_id=company.company_id,
        campaign_name=campaign_name,
        start_date=None,
        end_date=None,
        segments={},
        thread_id=thread_id  # <-- Вместо chat_id передаем thread_id
    )

    try:
        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)
        logger.info(f"Кампания успешно создана: id={new_campaign.campaign_id}, name={campaign_name}")
        return new_campaign
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Ошибка IntegrityError при создании кампании: {e}")
        raise ValueError("Ошибка при создании кампании.")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка SQLAlchemyError при создании кампании: {e}", exc_info=True)
        raise


def save_campaign_to_db(db: Session, company_id: int, campaign_data: dict) -> Campaigns:
    """
    Сохраняет новую кампанию в базу данных.

    :param db: Сессия базы данных.
    :param company_id: ID компании.
    :param campaign_data: Данные кампании (название, даты, параметры, сегменты, thread_id).
    :return: Объект Campaigns.
    """
    logger.debug(f"Начало сохранения кампании в БД. company_id={company_id}, campaign_data={campaign_data}")

    try:
        # Преобразование дат в формат YYYY-MM-DD
        start_date = datetime.strptime(campaign_data.get("start_date"), "%d.%m.%Y").strftime("%Y-%m-%d")
        end_date = (
            datetime.strptime(campaign_data.get("end_date"), "%d.%m.%Y").strftime("%Y-%m-%d")
            if campaign_data.get("end_date")
            else None
        )

        # Проверка, существует ли связанная тема
        thread_id = campaign_data.get("thread_id")
        chat_thread = db.query(ChatThread).filter_by(thread_id=thread_id).first()
        if not chat_thread:
            logger.error(f"Тема с thread_id={thread_id} не найдена. Кампания не может быть создана.")
            raise ValueError("Ошибка: Тема с указанным thread_id не существует.")

        # Создание кампании
        new_campaign = Campaigns(
            company_id=company_id,
            campaign_name=campaign_data.get("campaign_name"),
            start_date=start_date,
            end_date=end_date,
            params=campaign_data.get("params", {}),
            segments=campaign_data.get("filters", {}),
            thread_id=thread_id,
        )

        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)

        logger.info(
            f"Кампания успешно сохранена: id={new_campaign.campaign_id}, "
            f"name={new_campaign.campaign_name}, thread_id={thread_id}"
        )

        return new_campaign

    except IntegrityError as e:
        logger.error(f"Ошибка IntegrityError при сохранении кампании: {e}")
        db.rollback()
        raise ValueError("Ошибка при сохранении кампании. Возможно, такая кампания уже существует.")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemyError при сохранении кампании: {e}", exc_info=True)
        db.rollback()
        raise ValueError("Ошибка при сохранении кампании в базу данных.")


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