from aiogram import Router
from aiogram.types import Message, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from classifier import classify_message
from dispatcher import dispatch_classification  # Импорт диспетчера цепочек
from config import TARGET_CHAT_ID
from logger import logger

from utils.utils import extract_text_from_url, process_message, extract_text_from_document


router = Router()


def setup_handlers(dp):
    dp.include_router(router)


@router.message()
async def handle_message(message: Message, state: FSMContext):
    """
    Основной обработчик сообщений от пользователей.
    """
    # Проверяем ID чата
    if str(message.chat.id) != str(TARGET_CHAT_ID):
        logger.debug(f"Сообщение из неподдерживаемого чата: {message.chat.id}")
        return  # Игнорируем сообщение

    logger.debug(f"Получено сообщение: {message.text if message.text else 'нет текста'}")

    # Определяем тип сообщения (текст, файл или ссылка)
    try:
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

        # Передача результата классификации в диспетчер цепочек
        await dispatch_classification(classification, message, state)

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {str(e)}")
        await message.reply("Произошла ошибка при обработке вашего сообщения. Попробуйте снова.")


@router.chat_member()
async def greet_new_user(event: ChatMemberUpdated):
    """
    Обработчик добавления нового пользователя в чат.
    """
    if event.new_chat_member.status == "member" and event.old_chat_member.status in {"left", "kicked"}:
        user_name = event.new_chat_member.user.full_name
        chat_id = event.chat.id

        # Логируем добавление нового пользователя
        logger.debug(f"Пользователь {user_name} добавлен в чат {chat_id}. Отправляем приветственное сообщение.")

        # Отправляем приветственное сообщение
        await event.bot.send_message(
            chat_id=chat_id,
            text=f"Добро пожаловать, {user_name}! 👋\nРады видеть вас в нашем чате.")