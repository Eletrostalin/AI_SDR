from datetime import datetime

from aiogram import Router, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import os
import logging


from utils.states import AddEmailSegmentationState
from parser_email_table import process_email_table

logger = logging.getLogger(__name__)
router = Router()


@router.message()
async def handle_email_table_request(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления email-таблицы.
    """
    logger.info("Инициация добавления таблицы email. Установка состояния ожидания файла.")

    try:
        # Генерация имени таблицы
        user_id = message.from_user.id
        segment_table_name = generate_segment_table_name(user_id)

        # Сохранение состояния и данных
        await state.update_data(segment_table_name=segment_table_name)
        await state.set_state(AddEmailSegmentationState.waiting_for_file_upload)

        logger.debug(f"Состояние установлено: {await state.get_state()}")
        logger.debug(f"Сохранённые данные состояния: {await state.get_data()}")

        await message.reply(
            f"Пожалуйста, отправьте файл с email-таблицей в формате CSV или Excel. "
            f"Сегмент будет сохранён в таблице: `{segment_table_name}`."
        )

    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы: {e}")
        await message.reply("Произошла ошибка. Попробуйте позже.")


@router.message(StateFilter(AddEmailSegmentationState.waiting_for_file_upload))
async def handle_file_upload(message: Message, state: FSMContext):
    """
    Обработчик загрузки таблицы с данными для email-сегментации.
    """
    logger.debug(f"Получено сообщение: {message.text}. Текущее состояние: {await state.get_state()}")

    if not message.document:
        await message.reply("Пожалуйста, отправьте файл в формате CSV или Excel.")
        return

    document = message.document
    try:
        bot = message.bot
        file_path = os.path.join("uploads", document.file_name)
        await bot.download(document.file_id, destination=file_path)

        logger.info(f"Файл {document.file_name} сохранён в {file_path}.")

        # Получаем имя таблицы из состояния
        state_data = await state.get_data()
        segment_table_name = state_data.get("segment_table_name")
        logger.debug(f"Данные состояния: {state_data}")

        if not segment_table_name:
            raise ValueError("Название таблицы сегментации отсутствует в состоянии.")

        # Обрабатываем файл
        await process_email_table(file_path, segment_table_name, bot, message)
        await message.reply(f"Файл обработан успешно и сохранён в таблицу: `{segment_table_name}`.")
    except Exception as e:
        logger.error(f"Ошибка при обработке файла {document.file_name}: {e}")
        await message.reply(f"Ошибка при обработке файла: {str(e)}")
    finally:
        os.remove(file_path)

def generate_segment_table_name(company_id: int) -> str:
    """
    Генерирует имя таблицы на основе текущей даты и ID компании.

    :param company_id: ID компании.
    :return: Сформированное имя таблицы.
    """
    current_date = datetime.now().strftime("%Y%m%d")  # Форматируем текущую дату
    return f"{current_date}_{company_id}"