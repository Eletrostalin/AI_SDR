from datetime import datetime

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import os
import logging

from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.email_table_db import check_table_exists, get_table_data
from db.models import EmailTable
from utils.google_doc import create_excel_with_multiple_sheets
from states.states import AddEmailSegmentationState
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
        await state.clear()
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


async def handle_view_email_table(message: Message, state):
    """
    Обработчик для просмотра данных из всех таблиц сегментации email компании.

    :param message: Сообщение от пользователя.
    :param state: FSMContext для работы с состояниями.
    """
    chat_id = str(message.chat.id)  # Преобразование chat_id в строку
    db: Session = SessionLocal()

    try:
        # Получаем компанию по chat_id
        company = get_company_by_chat_id(db, chat_id)
        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return

        # Находим все email таблицы, связанные с компанией
        email_tables = db.query(EmailTable).filter(EmailTable.company_id == company.company_id).all()
        if not email_tables:
            await message.reply("Для вашей компании не найдено ни одной таблицы сегментации email.")
            return

        # Подготовка данных для Excel
        excel_data = {}
        for email_table in email_tables:
            table_name = email_table.table_name

            # Проверяем наличие таблицы в БД
            if not check_table_exists(db, table_name):
                logger.warning(f"Таблица {table_name} не найдена в базе данных.")
                continue

            # Извлекаем данные из таблицы
            data = get_table_data(db, table_name, limit=1000)
            if not data:
                logger.info(f"Таблица {table_name} пуста.")
                continue

            # Логируем извлеченные данные
            logger.debug(f"Данные для таблицы {table_name}: {data}")

            # Формируем данные для Excel
            headers = list(data[0].keys())  # Заголовки из первой строки
            rows = [headers] + [list(row.values()) for row in data]
            excel_data[table_name] = rows

        # Если нет данных для отправки
        if not excel_data:
            await message.reply("Ни одна из таблиц вашей компании не содержит данных.")
            return

        # Создаем общий Excel-документ с листами для каждой таблицы
        file_path = create_excel_with_multiple_sheets(excel_data, file_name=f"{company.name}_email_tables.xlsx")

        # Отправляем Excel-файл пользователю
        excel_file = FSInputFile(file_path)
        await message.reply_document(document=excel_file, caption="Вот данные из ваших таблиц сегментации email.")
    except Exception as e:
        logger.error(f"Ошибка при просмотре email таблиц компании: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса.")
    finally:
        db.close()