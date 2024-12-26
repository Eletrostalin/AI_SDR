from sqlalchemy.orm import Session
from datetime import datetime, date
from db.models import Campaigns, ChatThread, ContentPlan, Waves
from logger import logger
from sqlalchemy.exc import SQLAlchemyError


def get_chat_thread(db: Session, chat_id: int, thread_id: int) -> ChatThread:
    """
    Возвращает тему чата по chat_id и thread_id.
    """
    try:
        logger.debug(f"Получение темы чата: chat_id={chat_id}, thread_id={thread_id}")
        chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
        if not chat_thread:
            logger.error(f"Тема с chat_id={chat_id} и thread_id={thread_id} не найдена.")
        return chat_thread
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении темы чата: {e}", exc_info=True)
        return None


def get_campaign_by_thread_id(db: Session, thread_id: int) -> Campaigns:
    """
    Возвращает кампанию по thread_id.
    """
    try:
        logger.debug(f"Получение кампании по thread_id={thread_id}")
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            logger.error(f"Кампания с thread_id={thread_id} не найдена.")
        return campaign
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении кампании: {e}", exc_info=True)
        return None


def create_content_plan(db: Session, company_id: int, chat_id: int, description: str, wave_count: int,
                        campaign_id: int) -> ContentPlan:
    """
    Создает запись контентного плана.
    """
    try:
        logger.debug(f"Создание контентного плана для компании {company_id} и кампании {campaign_id}")
        content_plan = ContentPlan(
            company_id=company_id,
            telegram_id=str(chat_id),
            description=description,
            wave_count=wave_count,
            campaign_id=campaign_id
        )
        db.add(content_plan)
        db.commit()
        db.refresh(content_plan)
        logger.info(f"Контентный план создан: id={content_plan.content_plan_id}, description={description}")
        return content_plan
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при создании контентного плана: {e}", exc_info=True)
        db.rollback()
        return None


def parse_date_time(send_date: str, send_time: str) -> datetime:
    """
    Преобразует дату и время в объект datetime.
    """
    try:
        parsed_date = datetime.strptime(send_date, "%Y-%m-%d").date() if isinstance(send_date, str) else send_date
        parsed_time = datetime.strptime(send_time, "%H:%M:%S").time() if isinstance(send_time, str) else send_time
        return datetime.combine(parsed_date, parsed_time)
    except ValueError as e:
        logger.error(f"Ошибка преобразования даты и времени: {e}", exc_info=True)
        raise


def add_wave(db: Session, content_plan_id: int, company_id: int, campaign_id: int, wave: dict) -> Waves:
    """
    Добавляет волну к контентному плану.
    """
    try:
        logger.debug(f"Добавление волны: content_plan_id={content_plan_id}, wave={wave}")

        # Проверка наличия ключей
        if "send_time" not in wave or "send_date" not in wave or "subject" not in wave:
            raise ValueError("В wave отсутствуют необходимые ключи: 'send_time', 'send_date', 'subject'")

        # Преобразование даты и времени
        send_time = parse_date_time(wave["send_date"], wave["send_time"])
        subject = wave["subject"]

        if not subject.strip():
            raise ValueError("Поле 'subject' не может быть пустым.")

        # Создание новой волны
        new_wave = Waves(
            content_plan_id=content_plan_id,
            company_id=company_id,
            campaign_id=campaign_id,
            send_time=send_time,
            send_date=send_time.date(),
            subject=subject,
        )
        db.add(new_wave)
        db.flush()  # Применить изменения для получения ID волны
        logger.info(f"Волна добавлена: id={new_wave.wave_id}, subject={subject}")
        return new_wave
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Ошибка при добавлении волны: {e}", exc_info=True)
        db.rollback()
        return None


def get_content_plans_by_campaign_id(db: Session, campaign_id: int):
    """
    Возвращает список контентных планов для заданной кампании.

    :param db: Сессия базы данных SQLAlchemy.
    :param campaign_id: ID кампании.
    :return: Список объектов ContentPlan.
    """
    try:
        logger.debug(f"Получение контентных планов для campaign_id={campaign_id}")
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign_id).all()
        if not content_plans:
            logger.info(f"Для campaign_id={campaign_id} не найдено контентных планов.")
        return content_plans
    except Exception as e:
        logger.error(f"Ошибка при получении контентных планов для campaign_id={campaign_id}: {e}", exc_info=True)
        return []