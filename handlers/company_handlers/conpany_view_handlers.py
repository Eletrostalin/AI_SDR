import json
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from logger import logger
from db.db import SessionLocal
from db.db_company import (get_company_info_by_company_id,
                           get_company_by_chat_id)
from handlers.company_handlers.company_handlers import router


@router.message()
async def handle_view_company(message: Message, state: FSMContext):
    """
    Отображает информацию о компании на основе chat_id.
    """
    logger.debug("Запрос на отображение информации о компании.")
    chat_id = str(message.chat.id)
    db = SessionLocal()

    try:
        company = get_company_by_chat_id(db, chat_id)
        if not company:
            logger.warning(f"Компания с chat_id {chat_id} не найдена.")
            await message.reply("Компания не найдена. Возможно, вы ещё не добавили её.")
            return

        logger.debug(f"Компания найдена: {company}")
        company_info = get_company_info_by_company_id(db, company.company_id)
        if not company_info:
            logger.warning(f"Информация о компании с ID {company.company_id} отсутствует.")
            await message.reply("Информация о вашей компании отсутствует.")
            return

        await message.reply(
            "Информация о вашей компании:\n"
            "```json\n"
            f"{json.dumps(company_info, indent=4, ensure_ascii=False)}"
            "\n```",
            parse_mode="Markdown"
        )
        await state.clear()
        logger.debug(f"Информация о компании отправлена пользователю: {company_info}")

    except Exception as e:
        logger.error(f"Ошибка отображения информации о компании: {e}", exc_info=True)
        await message.reply(f"Ошибка при извлечении данных: {str(e)}")
    finally:
        db.close()