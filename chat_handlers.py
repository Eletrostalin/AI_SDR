from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from classifier import classify_message
from config import TARGET_CHAT_ID
import logging

from utils import extract_text_from_url, process_message, extract_text_from_document

logger = logging.getLogger(__name__)
router = Router()


def setup_handlers(dp):
    dp.include_router(router)


@router.message()
async def handle_message(message: Message):
    # Проверяем ID чата
    if str(message.chat.id) != str(TARGET_CHAT_ID):
        logger.debug(f"Сообщение из неподдерживаемого чата: {message.chat.id}")
        return  # Игнорируем сообщение

    logger.debug(f"Получено сообщение: {message.text if message.text else 'нет текста'}")

    # Определяем тип сообщения (текст, файл или ссылка)
    processed_message = await process_message(message, bot=message.bot)

    # Если это текстовое сообщение
    if processed_message["type"] == "text":
        logger.debug("Обрабатывается текстовое сообщение.")
        classification = classify_message(processed_message["content"])

    # Если это файл (документ)
    elif processed_message["type"] == "file":
        logger.debug(f"Обрабатывается файл: {processed_message['file_name']}")
        text = extract_text_from_document(
            processed_message["file_path"], processed_message["file_name"]
        )
        classification = classify_message(text)

    # Если это ссылка
    elif processed_message["type"] == "link":
        logger.debug(f"Обрабатывается ссылка: {processed_message['content']}")
        text = extract_text_from_url(processed_message["content"])
        classification = classify_message(text)

    else:
        logger.warning("Тип сообщения не распознан. Игнорируем.")
        await message.reply("Не удалось распознать тип сообщения. Отправьте текст, документ или ссылку.")
        return

    # Логируем результат классификации
    logger.debug(f"Результат классификации: {classification}")

    # Ответ на основе классификации
    if classification.get("action_type") == "unknown":
        await message.reply("Не удалось распознать сущность.")
    else:
        await message.reply(f"Распознаны данные:\n{classification}")
        print(classification)  # Отладочный вывод JSON


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated):
    # Проверяем, добавлен ли пользователь в чат
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        user_name = event.new_chat_member.user.full_name
        chat_id = event.chat.id

        # Логируем добавление нового пользователя
        logger.debug(f"Пользователь {user_name} добавлен в чат {chat_id}. Отправляем приветственное сообщение.")

        # Отправляем приветственное сообщение
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"Добро пожаловать, {user_name}! 👋\nРады видеть вас в нашем чате.")