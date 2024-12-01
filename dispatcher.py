from db.db import SessionLocal
from handlers.campaign_delete_handler import handle_delete_campaign_request
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from handlers.company_handlers import handle_add_company, handle_view_company, handle_edit_company, \
    handle_delete_company
from handlers.campaign_handlers import handle_add_campaign, handle_view_campaigns
from logger import logger


async def dispatch_classification(classification: dict, message: Message, state: FSMContext):
    """
    Направляет запрос пользователя в соответствующий обработчик на основе классификации.

    :param classification: Результат классификации (JSON).
    :param message: Сообщение пользователя.
    :param state: Состояние FSMContext.
    """
    action_type = classification.get("action_type")
    entity_type = classification.get("entity_type")

    # Создаем сессию для работы с базой данных
    db = SessionLocal()

    try:
        if action_type == "add" and entity_type == "company":
            await handle_add_company(message, state)
        elif action_type == "view" and entity_type == "company":
            await handle_view_company(message)
        elif action_type == "edit" and entity_type == "company":
            await handle_edit_company(message, state)
        elif action_type == "delete" and entity_type == "company":
            await handle_delete_company(message, state)
        elif action_type == "add" and entity_type == "campaign":
            await handle_add_campaign(message, state)
        elif action_type == "view" and entity_type == "campaign":
            await handle_view_campaigns(message, state)
        elif action_type == "delete" and entity_type == "campaign":
            await handle_delete_campaign_request(message, state)
        else:
            logger.warning(f"Не удалось обработать запрос: {classification}")
            await message.reply("К сожалению, я не могу обработать ваш запрос. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка в обработке классификации: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса. Попробуйте снова.")
    finally:
        db.close()