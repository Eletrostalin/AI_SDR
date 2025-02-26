import pandas as pd
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile
from sqlalchemy.orm import Session
import os
import logging

from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.email_table_db import check_table_exists, get_table_data
from db.models import EmailTable
from utils.google_doc import create_excel_with_multiple_sheets
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from states.states import AddEmailSegmentationState
from utils.parser_email_table import save_cleaned_data, clean_dataframe, map_columns, clean_and_validate_emails
from utils.segment_utils import generate_segment_table_name

logger = logging.getLogger(__name__)
router = Router()


@router.message()
async def handle_email_table_request(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления email-таблицы.
    """
    logger.info("Инициация добавления таблицы email. Установка состояния ожидания файла.")

    try:
        chat_id = message.chat.id

        # Получаем company_id
        with SessionLocal() as db:
            company = get_company_by_chat_id(db, str(chat_id))
            if not company:
                logger.error(f"❌ Ошибка: Не найден company_id для chat_id={chat_id}")
                await message.reply("❌ Ошибка: Не удалось найти компанию, связанный с вашим чатом.")
                return

            company_id = company.company_id  # company.id должен быть целым числом
            logger.debug(f"🔹 Найден company_id={company_id} для chat_id={chat_id}")

        segment_table_name = generate_segment_table_name(chat_id)
        if segment_table_name is None:
            logger.error("❌ Ошибка: segment_table_name не был сгенерирован!")
            return

        logger.debug(f"📌 Сгенерированное имя таблицы: {segment_table_name}")

        # Сохранение состояния и данных
        await state.update_data(segment_table_name=segment_table_name)
        await state.set_state(AddEmailSegmentationState.waiting_for_file_upload)

        logger.debug(f"Состояние установлено: {await state.get_state()}")
        logger.debug(f"Сохранённые данные состояния: {await state.get_data()}")

        await message.reply(
            f"Для запуска рассылок мне нужна база адресов электронной почты.Пожалуйста, загрузите файл 📂 с емейлами в "
            f"формате XLSX"
        )

    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы: {e}")
        await message.reply("Произошла ошибка. Попробуйте позже.")


@router.message(StateFilter(AddEmailSegmentationState.waiting_for_file_upload))
async def handle_file_upload(message: Message, state: FSMContext):
    """
    Обработчик загрузки таблицы с email-сегментацией.
    """
    logger.debug(f"📂 Получено сообщение. Текущее состояние: {await state.get_state()}")

    # Если пользователь отправил сообщение без файла
    if not message.document:
        logger.warning("⚠️ Пользователь отправил сообщение без файла.")
        await message.reply("❌ Пожалуйста, отправьте файл в формате Excel (.xlsx, .xls).")
        return

    document = message.document
    file_path = os.path.join("uploads", document.file_name)

    try:
        allowed_extensions = (".xlsx", ".xls")
        if not document.file_name.lower().endswith(allowed_extensions):
            await message.reply("❌ Неподдерживаемый формат файла. Загрузите Excel (.xlsx, .xls).")
            return

        bot = message.bot

        os.makedirs("uploads", exist_ok=True)
        logger.info("✅ Директория 'uploads' проверена/создана.")

        await bot.download(document.file_id, destination=file_path)
        logger.info(f"📂 Файл {document.file_name} успешно сохранён в {file_path}.")

        # Получаем данные из state
        state_data = await state.get_data()
        segment_table_name = state_data.get("segment_table_name")

        # Если segment_table_name отсутствует, генерируем заново
        if segment_table_name is None:
            chat_id = message.chat.id

            with SessionLocal() as db:
                company = get_company_by_chat_id(db, str(chat_id))
                if not company:
                    logger.error(f"❌ Ошибка: Не найден company_id для chat_id={chat_id}")
                    await message.reply("❌ Ошибка: Не удалось найти компанию, связанную с вашим чатом.")
                    return

                company_id = company.company_id  # Исправлено!
                segment_table_name = generate_segment_table_name(company_id)
                logger.debug(f"🔄 Повторное создание имени таблицы: {segment_table_name}")

            # Обновляем state с новым segment_table_name
            await state.update_data(segment_table_name=segment_table_name)

        logger.debug(f"📌 Используемое имя таблицы: {segment_table_name}")

        # Обрабатываем файл
        is_processed = await process_email_table(file_path, segment_table_name, message, state)

        if is_processed is True:
            await message.reply(f"✅ Файл обработан успешно и сохранён в таблицу: `{segment_table_name}`.")
        elif is_processed is None:  # 🔄 Новый кейс
            logger.info("⚠️ Ожидание выбора пользователя по дубликатам email.")
        else:
            logger.warning(f"⚠️ Ошибки при обработке файла {document.file_name}.")
            await message.reply("⚠️ Ошибка при обработке файла. Проверьте данные и попробуйте ещё раз.")

        await state.clear()

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке файла {document.file_name}: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка при обработке файла: {e}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑 Файл {file_path} удалён.")
        else:
            logger.warning(f"⚠️ Файл {file_path} не найден, удаление пропущено.")


def get_email_choice_keyboard():
    """Создаёт инлайн-кнопки для выбора способа обработки email."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оставить (разделить записи)", callback_data="split_emails")],
            [InlineKeyboardButton(text="❌ Изменить (загрузить новый файл)", callback_data="upload_new_file")]
        ]
    )


async def process_email_table(file_path: str, segment_table_name: str, message: Message, state: FSMContext) -> bool:
    """
    Обрабатывает загруженную таблицу Excel, выполняет маппинг колонок, очищает данные и сохраняет их в базу.
    """
    try:
        df = pd.read_excel(file_path)
        if df.empty:
            await message.reply("❌ Файл пуст или не содержит данных.")
            return False

        df = clean_dataframe(df)
        if df.empty:
            await message.reply("❌ Файл не содержит значимых данных после очистки. Проверьте его содержимое.")
            return False

        user_columns = df.columns.tolist()
        logger.debug(f"📊 Колонки пользователя: {user_columns}")

        mapping = await map_columns(user_columns)
        if not mapping:
            await message.reply("❌ Не удалось сопоставить загруженные данные с фиксированными колонками.")
            return False

        df.rename(columns=mapping, inplace=True)
        logger.info(f"✅ Колонки после маппинга: {df.columns.tolist()}")

        df, valid_emails, multi_email_rows, problematic_rows, problematic_values, empty_email_rows = clean_and_validate_emails(df)

        # Если в файле нет колонки с email, прерываем обработку
        if valid_emails is None:
            await message.reply("❌ Ошибка: В загружаемой таблице не найдена колонка e-mail.")
            return False

        # Уведомление о количестве пустых email, но продолжаем обработку
        if empty_email_rows > 0:
            await message.reply(
                f"⚠️ В загруженном файле найдено **{empty_email_rows}** строк без email. "
                "Они не будут сохранены, но остальная информация будет обработана."
            )

        # Если есть дубликаты email, ждем ответа пользователя
        if multi_email_rows > 0:
            logger.warning(f"⚠️ Найдено {multi_email_rows} записей с несколькими email. "
                           f"Номера строк: {problematic_rows}. Значения: {problematic_values}")

            await state.update_data(
                processing_df=df,
                email_column=valid_emails,
                segment_table_name=segment_table_name,
                problematic_rows=problematic_rows,
                problematic_values=problematic_values
            )

            logger.debug(f"🔄 Устанавливаем состояние: {AddEmailSegmentationState.duplicate_email_check}")
            await state.set_state(AddEmailSegmentationState.duplicate_email_check)
            logger.debug(f"✅ Установлено состояние: {await state.get_state()}")

            # Подготовка значений для вывода в Telegram
            values_display = "\n".join([f"🔹 **Строка {row}**: `{val}`" for row, val in zip(problematic_rows, problematic_values)])

            await message.reply(
                f"⚠️ В загруженном файле обнаружено **{multi_email_rows}** записей с несколькими email в одной ячейке.\n\n"
                f"{values_display}\n\n"
                "Выберите, как поступить:",
                reply_markup=get_email_choice_keyboard()
            )
            return False  # Ждём ответа пользователя

        # Фильтруем строки, удаляя те, где email пустой
        df = df[df[valid_emails] != ""]

        await save_cleaned_data(df, segment_table_name, message)
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке файла {file_path}: {e}", exc_info=True)
        await message.reply(f"❌ Произошла ошибка при обработке файла: {e}")
        return False


@router.callback_query()
async def handle_email_choice_callback(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя: разделить email-адреса или запросить новый файл (инлайн-кнопки).
    """
    logger.debug(f"🎯 Получен колбек: {call.data}")

    choice = call.data
    data = await state.get_data()
    df = data.get("processing_df")
    email_column = data.get("email_column")
    segment_table_name = data.get("segment_table_name")  # Извлекаем имя таблицы

    if choice == "split_emails":
        logger.info("✅ Пользователь выбрал разделение записей с несколькими email.")

        df = df.assign(**{email_column: df[email_column].str.split(r"[;, ]")}).explode(email_column)
        df[email_column] = df[email_column].str.strip()

        await call.message.edit_text("✅ Записи разделены! Теперь каждая строка содержит только **один** email.")

        await save_cleaned_data(df, segment_table_name, call.message)
        await state.clear()

    elif choice == "upload_new_file":
        logger.info("🔄 Пользователь решил загрузить новый файл.")

        # Сохраняем имя таблицы перед сменой состояния!
        await state.update_data(segment_table_name=segment_table_name, waiting_for_new_file=True)

        await state.set_state(AddEmailSegmentationState.waiting_for_file_upload)
        await call.message.edit_text("🔄 Пожалуйста, загрузите исправленный файл.")

    else:
        await call.answer("❌ Неверный выбор.", show_alert=True)


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