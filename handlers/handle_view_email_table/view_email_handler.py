from aiogram.types import FSInputFile
from sqlalchemy.orm import Session
import logging

from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.email_table_db import check_table_exists, get_table_data
from db.models import EmailTable
from utils.google_doc import create_excel_with_multiple_sheets
from aiogram import Router
from aiogram.types import  Message


logger = logging.getLogger(__name__)
router = Router()

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
        company = get_company_by_chat_id(db, str(chat_id))
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