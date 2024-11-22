from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from classifier import classify_message
from config import TARGET_CHAT_ID
import logging

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

    # Проверяем, есть ли текстовое сообщение
    if not message.text:
        logger.debug("Получено сообщение без текста. Игнорируем.")
        return

    logger.debug(f"Получено сообщение: {message.text}")

    # Передача сообщения на классификацию
    classification = await classify_message(message.text)  # Добавлено await
    logger.debug(f"Результат классификации: {classification}")

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