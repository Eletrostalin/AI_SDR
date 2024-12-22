from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from chat_handlers import router
from db.models import CompanyInfo
from logger import logger
from db.db import SessionLocal
from db.db_company import (get_company_by_chat_id,
                           delete_additional_info)


@router.message()
async def handle_delete_additional_info(message: Message, state: FSMContext):
    """
    Удаляет содержимое колонки `additional_info` для компании.
    """
    db = SessionLocal()
    try:
        chat_id = str(message.chat.id)
        company = get_company_by_chat_id(db, chat_id)

        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы добавили данные компании.")
            return

        # Проверяем, есть ли информация для удаления
        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()

        if not company_info or not company_info.additional_info:
            await message.reply("Дополнительная информация уже отсутствует.")
            return

        # Удаляем данные из `additional_info`
        delete_additional_info(db, company.company_id)
        await message.reply("Дополнительная информация успешно удалена.")

        # Сбрасываем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при удалении дополнительной информации: {e}", exc_info=True)
        await message.reply("Произошла ошибка при удалении дополнительной информации. Попробуйте снова.")
    finally:
        db.close()