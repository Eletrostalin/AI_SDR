from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from db.models import Campaigns, ChatThread
from logger import logger


async def create_campaign_and_thread(bot, db, chat_id, campaign_name):
    """
    Создает новую кампанию и новую форумную тему в Telegram.

    :param bot: Объект бота
    :param db: Сессия БД
    :param chat_id: ID чата, в котором создается кампания
    :param campaign_name: Название кампании
    :return: Объект новой кампании
    """
    try:
        # Находим компанию по chat_id
        company = db.execute(
            text("SELECT company_id FROM companies WHERE chat_id = :chat_id"),
            {"chat_id": str(chat_id)}
        ).fetchone()

        if not company:
            logger.error(f"❌ Ошибка: Компания не найдена для chat_id={chat_id}")
            raise ValueError("Компания не найдена.")

        company_id = company[0]

        # ✅ Всегда создаем новую тему в Telegram
        try:
            topic = await bot.create_forum_topic(chat_id=chat_id, name=campaign_name)
            thread_id = topic.message_thread_id
            logger.info(f"✅ Создана новая тема: thread_id={thread_id}, chat_id={chat_id}")

            # ✅ Сохраняем тему в БД
            db.execute(
                text(
                    "INSERT INTO chat_threads (chat_id, thread_id, thread_name) VALUES (:chat_id, :thread_id, :thread_name)"),
                {"chat_id": chat_id, "thread_id": thread_id, "thread_name": campaign_name}
            )
            db.commit()

        except Exception as e:
            logger.error(f"❌ Ошибка при создании темы в Telegram: {e}", exc_info=True)
            raise ValueError("Ошибка при создании темы чата в Telegram.")

        # ✅ Проверяем, есть ли уже кампания с таким thread_id
        existing_campaign = db.execute(
            text("SELECT campaign_id FROM campaigns WHERE thread_id = :thread_id"),
            {"thread_id": thread_id}
        ).fetchone()

        if existing_campaign:
            logger.warning(f"⚠️ Кампания уже существует для темы thread_id={thread_id}. Используем её.")
            campaign_id = existing_campaign[0]
            return db.query(Campaigns).filter_by(campaign_id=campaign_id).first()

        # ✅ Создаем новую кампанию
        new_campaign = Campaigns(
            company_id=company_id,
            thread_id=thread_id,
            campaign_name=campaign_name,
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