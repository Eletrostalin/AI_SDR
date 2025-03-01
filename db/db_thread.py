from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from db.models import ChatThread
from logger import logger


def save_thread_to_db(db: Session, chat_id: str, thread_id: int, thread_name: str) -> ChatThread:
    """
    Сохраняет тему в базу данных.

    :param db: Сессия базы данных.
    :param chat_id: ID чата.
    :param thread_id: ID темы.
    :param thread_name: Название темы.
    :return: Объект ChatThread.
    """
    try:
        new_thread = ChatThread(
            chat_id=chat_id,
            thread_id=thread_id,
            thread_name=thread_name,
        )
        db.add(new_thread)
        db.commit()
        db.refresh(new_thread)
        logger.info(f"Тема сохранена: chat_id={chat_id}, thread_id={thread_id}")
        return new_thread
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка сохранения темы в БД: {e}")
        raise ValueError("Ошибка при сохранении темы в базу данных.")


def get_thread_by_chat_id(db: Session, chat_id: str) -> ChatThread | None:
    """
    Получает тему по chat_id.

    :param db: Сессия базы данных.
    :param chat_id: ID чата.
    :return: Объект ChatThread или None.
    """
    return db.query(ChatThread).filter_by(chat_id=chat_id).first()


def get_thread_by_thread_id(db: Session, thread_id: int) -> ChatThread | None:
    """
    Получает тему по thread_id.

    :param db: Сессия базы данных.
    :param thread_id: ID темы.
    :return: Объект ChatThread или None.
    """
    return db.query(ChatThread).filter_by(thread_id=thread_id).first()


def delete_thread(db: Session, thread_id: int) -> None:
    """
    Удаляет тему из базы.

    :param db: Сессия базы данных.
    :param thread_id: ID темы.
    """
    thread = get_thread_by_thread_id(db, thread_id)
    if thread:
        db.delete(thread)
        db.commit()
        logger.info(f"Тема удалена: thread_id={thread_id}")
    else:
        logger.warning(f"Тема с thread_id={thread_id} не найдена.")