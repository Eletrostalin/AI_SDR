from db.db import SessionLocal
from handlers.campaign_handlers.campaign_delete_handler import handle_delete_campaign_request
from handlers.campaign_handlers.campaign_view_handler import handle_view_campaigns
from handlers.company_handlers import handle_view_company, handle_edit_company, handle_delete_additional_info
from handlers.campaign_handlers.campaign_handlers import handle_add_campaign
from handlers.content_plan_handlers import handle_add_content_plan
from handlers.email_table_handler import handle_email_table_request, handle_view_email_table
from handlers.segmentation_handlers import handle_create_segment
from logger import logger

from sqlalchemy.orm import Session
from db.models import ChatThread
from aiogram.types import Message
from aiogram.fsm.context import FSMContext


async def get_thread_name(db: Session, chat_id: int, thread_id: int) -> str:
    """
    Получает название темы по chat_id и thread_id из базы данных.

    :param db: Сессия базы данных.
    :param chat_id: ID чата.
    :param thread_id: ID темы.
    :return: Название темы или None, если тема не найдена.
    """
    thread = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
    return thread.thread_name if thread else None


async def dispatch_classification(classification: dict, message: Message, state: FSMContext):
    """
    Направляет запрос пользователя в соответствующий обработчик на основе классификации и темы чата.

    :param classification: Результат классификации (JSON).
    :param message: Сообщение пользователя.
    :param state: Состояние FSMContext.
    """
    action_type = classification.get("action_type")
    entity_type = classification.get("entity_type")

    # Создаем сессию для работы с базой данных
    db = SessionLocal()
    try:
        thread_id = message.message_thread_id
        chat_id = message.chat.id

        if thread_id:
            # Получаем название темы из базы данных
            thread_name = await get_thread_name(db, chat_id, thread_id)
        else:
            thread_name = "general"  # Если thread_id нет, считаем, что это general

        logger.debug(f"Сообщение из темы: {thread_name}")

        if thread_name == "general":
            # Обрабатываем все типы действий
            if action_type == "add" and entity_type == "company":
                await handle_edit_company(message, state)
            elif action_type == "view" and entity_type == "company":
                await handle_view_company(message, state)
            elif action_type == "edit" and entity_type == "company":
                await handle_edit_company(message, state)
            elif action_type == "delete" and entity_type == "company":
                await handle_delete_additional_info(message, state)
            elif action_type == "add" and entity_type == "campaign":
                await handle_add_campaign(message, state)
            elif action_type == "view" and entity_type == "campaign":
                await handle_view_campaigns(message, state)
            elif action_type == "delete" and entity_type == "campaign":
                await handle_delete_campaign_request(message, state)
            elif action_type == "add" and entity_type == "email_table":
                await handle_email_table_request(message, state)
            elif action_type == "view" and entity_type == "email_table":
                await handle_view_email_table(message, state)  # Новый обработчик
             # Новый обработчик для просмотра сегментации
            # elif action_type == "delete" and entity_type == "segment":
            #     await handle_delete_segment(message, state)  # Новый обработчик для удаления сегмента
            # elif action_type == "add" and entity_type == "content_plan":
            #     await handle_add_content_plan(message, state)  # Новый обработчик для content_plan
            else:
                logger.warning(f"Не удалось обработать запрос: {classification}")
                await message.reply("К сожалению, я не могу обработать ваш запрос. Попробуйте снова.")
        else:
            # Если тема не general
            if action_type == "delete" and entity_type == "campaign":
                await handle_delete_campaign_request(message, state)
            elif action_type == "add" and entity_type == "content_plan":
                await handle_add_content_plan(message, state)  # Допустим, content_plan можно создавать в других темах
            elif action_type == "add" and entity_type == "segment":
                await handle_create_segment(message, state)
            else:
                await message.reply(
                    "Эта операция доступна только в теме general. Пожалуйста, перейдите в основную тему и повторите запрос."
                )
    except Exception as e:
        logger.error(f"Ошибка в обработке классификации: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса. Попробуйте снова.")
    finally:
        db.close()