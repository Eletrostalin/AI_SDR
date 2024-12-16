from aiogram import Bot
from aiogram.types import Chat
from sqlalchemy.orm import Session
from db.models import ChatThread
from logger import logger

# Создание темы ботом при инициализации
async def create_new_thread(bot: Bot, chat_id: int, thread_name: str):
    """
    Создание новой темы в супергруппе.
    :param bot: Экземпляр бота
    :param chat_id: ID чата (супергруппы)
    :param thread_name: Название темы
    :return: ID созданной темы или None в случае ошибки
    """
    logger.debug(f"Попытка создания новой темы '{thread_name}' в чате {chat_id}.")
    try:
        new_thread = await bot.create_forum_topic(chat_id, name=thread_name)
        logger.info(f"Создана новая тема '{thread_name}' в чате {chat_id}. ID темы: {new_thread.message_thread_id}")
        return new_thread.message_thread_id  # Возвращаем ID созданной темы
    except Exception as e:
        logger.error(f"Ошибка создания темы '{thread_name}' в чате {chat_id}: {e}", exc_info=True)
        return None


async def create_thread(bot, chat_id, thread_name):
    """
    Создает тему в чате и возвращает ID созданной темы.

    :param bot: Объект бота
    :param chat_id: ID чата
    :param thread_name: Название создаваемой темы
    :return: ID созданной темы или None в случае ошибки
    """
    logger.debug(f"Запуск функции create_thread: chat_id={chat_id}, thread_name='{thread_name}'")
    try:
        # Создаем тему
        created_topic = await bot.create_forum_topic(chat_id=chat_id, name=thread_name)
        logger.info(f"Тема '{thread_name}' успешно создана. ID темы: {created_topic.message_thread_id}")
        return created_topic.message_thread_id  # Возвращаем ID созданной темы
    except Exception as e:
        logger.error(f"Ошибка при создании темы '{thread_name}' в чате {chat_id}: {e}", exc_info=True)
        return None
