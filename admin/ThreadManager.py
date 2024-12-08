from aiogram import Bot
from aiogram.types import Chat
from sqlalchemy.orm import Session
from db.models import ChatThread
from logger import logger





async def create_new_thread(bot: Bot, chat_id: int, thread_name: str):
    """
    Создание новой темы в супергруппе.
    :param bot: Экземпляр бота
    :param chat_id: ID чата (супергруппы)
    :param thread_name: Название темы
    :return: ID созданной темы или None в случае ошибки
    """
    try:
        new_thread = await bot.create_forum_topic(chat_id, name=thread_name)
        logger.info(f"Создана новая тема '{thread_name}' в чате {chat_id}.")
        return new_thread.message_thread_id  # Возвращаем ID созданной темы
    except Exception as e:
        logger.error(f"Ошибка создания темы '{thread_name}' в чате {chat_id}: {e}")
        return None

def save_thread_to_db(db: Session, chat_id: int, thread_id: int, thread_name: str):
    """
    Сохраняет информацию о теме в базу данных.
    """
    try:
        thread_exists = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
        if not thread_exists:
            new_thread = ChatThread(
                chat_id=chat_id,
                thread_id=thread_id,
                thread_name=thread_name
            )
            db.add(new_thread)
            db.commit()
            logger.info(f"Тема '{thread_name}' сохранена в базу данных.")
    except Exception as e:
        logger.error(f"Ошибка сохранения темы '{thread_name}' в базу данных: {e}", exc_info=True)