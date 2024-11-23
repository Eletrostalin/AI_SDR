from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from handlers.company_handlers import handle_add_company


async def dispatch_classification(classification: dict, message: Message, state: FSMContext):
    """
    Направляет запрос пользователя в соответствующий обработчик на основе классификации.

    :param classification: Результат классификации (JSON).
    :param message: Сообщение пользователя.
    :param state: Состояние FSMContext.
    """
    action_type = classification.get("action_type")
    entity_type = classification.get("entity_type")

    # Сортировка по действиям и сущностям
    if action_type == "add" and entity_type == "company":
        # Обработка добавления компании
        await handle_add_company(message, state)
    elif action_type == "view" and entity_type == "company":
        # Пример обработки просмотра компаний
        await message.reply("Отображение списка компаний.")
    else:
        # Если ничего не подошло
        await message.reply(f"Не удалось обработать запрос: {classification}")