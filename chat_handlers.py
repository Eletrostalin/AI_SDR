from aiogram import Router, F
from aiogram.types import Message
from chain_dispatcher import ChainDispatcher

# Инициализация маршрутизатора и диспетчера цепочек
router = Router()
dispatcher = ChainDispatcher()

# Ограничение на ID чата, в котором бот будет работать
TARGET_CHAT_ID = "ID_ВАШЕГО_ЧАТА"

@router.message(F.chat.id == TARGET_CHAT_ID)  # Обработчик сообщений в заданном чате
async def handle_chat_message(message: Message):
    """
    Обрабатывает сообщения от пользователей в заданном чате, направляет их в ChainDispatcher,
    который определяет и вызывает нужную цепочку для обработки запроса.
    """
    # Получаем текст сообщения от пользователя
    user_query = message.text

    # Передаем запрос в ChainDispatcher для классификации и маршрутизации
    response = await dispatcher.route_request(user_query)

    # Отправляем ответ в чат
    await message.answer(response)