import pandas as pd
from aiogram.filters import StateFilter
from aiogram import F
from sqlalchemy.orm import Session
import os
import logging

from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from handlers.campaign_handlers.campaign_handlers import handle_add_campaign
from states.states import EmailUploadState, EmailProcessingDecisionState
from utils.parser_email_table import save_cleaned_data, clean_dataframe, map_columns, clean_and_validate_emails
from utils.segment_utils import generate_segment_table_name

logger = logging.getLogger(__name__)
router = Router()

def get_first_question_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для первого вопроса о загрузке еще одного файла."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="load_more_files")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="ask_campaign_question")]
        ]
    )

def get_second_question_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для второго вопроса о начале кампании."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="proceed_to_campaign")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="go_back_to_upload")]
        ]
    )


def get_email_choice_keyboard():
    """Создаёт инлайн-кнопки для выбора способа обработки email."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Оставить (разделить записи)", callback_data="split_emails")],
            [InlineKeyboardButton(text="❌ Изменить (загрузить новый файл)", callback_data="upload_new_file")]
        ]
    )


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
        await state.set_state(EmailUploadState.waiting_for_file_upload)

        logger.debug(f"Состояние установлено: {await state.get_state()}")
        logger.debug(f"Сохранённые данные состояния: {await state.get_data()}")

        await message.reply(
            f"Для запуска рассылок мне нужна база адресов электронной почты.Пожалуйста, загрузите файл 📂 с емейлами в "
            f"формате XLSX"
        )

    except Exception as e:
        logger.error(f"Ошибка при инициализации таблицы: {e}")
        await message.reply("Произошла ошибка. Попробуйте позже.")


@router.message(StateFilter(EmailUploadState.waiting_for_file_upload))
async def handle_file_upload(message: Message, state: FSMContext):
    """
    Обработчик загрузки таблицы с email-сегментацией.
    """
    logger.debug(f"Получено сообщение. Текущее состояние: {await state.get_state()}")
    await message.reply(f"Начинаю обработку таблицы, это может занять некоторое время...")

    if not message.document:
        logger.warning("Пользователь отправил сообщение без файла.")
        await message.reply("Пожалуйста, отправьте файл в формате Excel (.xlsx, .xls).")
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

        # 🔹 **Сохраняем `file_name` в состояние FSM**
        await state.update_data(file_name=document.file_name)

        # 🔹 Проверяем, сохранился ли file_name корректно
        state_data = await state.get_data()
        if not state_data.get("file_name"):
            logger.error("❌ Ошибка: file_name не был сохранён в FSMContext!")
        else:
            logger.debug(f"✅ file_name сохранён: {state_data.get('file_name')}")

        # Получаем данные из state
        state_data = await state.get_data()
        segment_table_name = state_data.get("segment_table_name")

        if segment_table_name is None:
            chat_id = message.chat.id

            with SessionLocal() as db:
                company = get_company_by_chat_id(db, str(chat_id))
                if not company:
                    logger.error(f"❌ Ошибка: Не найден company_id для chat_id={chat_id}")
                    await message.reply("❌ Ошибка: Не удалось найти компанию, связанную с вашим чатом.")
                    return

                company_id = company.company_id
                segment_table_name = generate_segment_table_name(company_id)
                logger.debug(f"🔄 Повторное создание имени таблицы: {segment_table_name}")

            await state.update_data(segment_table_name=segment_table_name)

        logger.debug(f"📌 Используемое имя таблицы: {segment_table_name}")

        # Обрабатываем файл
        is_processed = await process_email_table(file_path, segment_table_name, message, state)

        if is_processed:
            await message.reply(f"✅ Файл обработан успешно.")
            await ask_about_more_files(message, state)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке файла {document.file_name}: {e}", exc_info=True)
        await message.reply(f"❌ Ошибка при обработке файла: {e}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"🗑 Файл {file_path} удалён.")
        else:
            logger.warning(f"⚠️ Файл {file_path} не найден, удаление пропущено.")


async def process_email_table(file_path: str, segment_table_name: str, message: Message, state: FSMContext) -> bool:
    """
    Обрабатывает загруженную таблицу Excel, выполняет маппинг колонок, очищает данные и сохраняет их в базу.
    """
    try:
        df = pd.read_excel(file_path)
        logger.debug(f"📊 Исходные данные (первые 5 строк):\n{df.head()}")

        if df.empty:
            await message.reply("❌ Файл пуст или не содержит данных.")
            return False

        df = clean_dataframe(df)
        logger.debug(f"📊 Данные после очистки (первые 5 строк):\n{df.head()}")

        if df.empty:
            await message.reply("❌ Файл не содержит значимых данных после очистки. Проверьте его содержимое.")
            return False

        user_columns = df.columns.tolist()
        logger.debug(f"📊 Колонки пользователя перед маппингом: {user_columns}")

        mapping = await map_columns(user_columns)
        logger.debug(f"🎯 Полученный маппинг колонок: {mapping}")

        if not mapping:
            await message.reply("❌ Не удалось сопоставить загруженные данные с фиксированными колонками.")
            return False

        df.rename(columns=mapping, inplace=True)
        logger.debug(f"📊 Данные после маппинга (первые 5 строк):\n{df.head()}")

        state_data = await state.get_data()
        file_name = state_data.get("file_name")

        if not file_name:
            await message.reply("❌ Ошибка: не удалось определить имя файла.")
            return False

        df["file_name"] = file_name  # ✅ Добавляем колонку с именем файла
        logger.debug(f"📌 Добавлен file_name в DataFrame: {file_name}")

        # 🔹 Фильтруем: оставляем только строки, где email содержит "@"
        if "email" in df.columns:
            total_rows = len(df)
            logger.debug(f"📊 Количество строк перед фильтрацией email: {total_rows}")

            df = df[df["email"].astype(str).str.contains("@", na=False)]
            filtered_out_rows = total_rows - len(df)

            if filtered_out_rows > 0:
                logger.warning(f"⚠️ Исключено {filtered_out_rows} строк без корректного email.")

            if df.empty:
                await message.reply("❌ В загружаемом файле не найдено валидных email-адресов.")
                return False

        df, valid_emails, multi_email_rows, problematic_rows, problematic_values = clean_and_validate_emails(df)
        logger.debug(f"📊 Данные после валидации email (первые 5 строк):\n{df.head()}")

        if valid_emails is None:
            await message.reply("❌ Ошибка: В загружаемой таблице не найдена колонка email.")
            return False

        logger.info(f"📥 Подготовлено {len(df)} строк для сохранения в таблицу {segment_table_name}")

        save_result = await save_cleaned_data(df, segment_table_name, message, state)
        if save_result:
            logger.info(f"✅ Данные успешно сохранены в {segment_table_name}")
        else:
            logger.error(f"❌ Ошибка при сохранении данных в {segment_table_name}")

        return save_result

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке файла {file_path}: {e}", exc_info=True)
        return False


@router.callback_query(StateFilter(EmailUploadState.duplicate_email_check))
async def handle_email_choice_callback(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя: разделить email-адреса или запросить новый файл.
    """
    current_state = await state.get_state()
    logger.debug(f"📌 Текущее состояние перед обработкой колбэка: {current_state}")
    logger.debug(f"🎯 Получен колбек: {call.data}")

    choice = call.data
    data = await state.get_data()
    df = data.get("processing_df")
    email_column = data.get("email_column")
    segment_table_name = data.get("segment_table_name")

    if choice == "split_emails":
        logger.info("✅ Пользователь выбрал разделение записей с несколькими email.")
        df = df.assign(**{email_column: df[email_column].str.split(r"[;, ]")}).explode(email_column)
        df[email_column] = df[email_column].str.strip()

        await call.message.edit_text("✅ Записи разделены! Теперь каждая строка содержит только **один** email.")

        await save_cleaned_data(df, segment_table_name, call.message, state)
        await ask_about_more_files(call.message, state)

    elif choice == "upload_new_file":
        logger.info("🔄 Пользователь решил загрузить новый файл.")
        await state.set_state(EmailUploadState.waiting_for_file_upload)
        await call.message.edit_text("🔄 Пожалуйста, загрузите исправленный файл.")

    else:
        await call.answer("❌ Неверный выбор.", show_alert=True)


async def ask_about_more_files(message: Message, state: FSMContext):
    """
    Спрашивает пользователя, хочет ли он загрузить еще один файл.
    """
    logger.debug(f"🔄 Устанавливаем состояние: {EmailProcessingDecisionState.waiting_for_more_files_decision}")
    await state.set_state(EmailProcessingDecisionState.waiting_for_more_files_decision)

    current_state = await state.get_state()
    logger.debug(f"✅ После паузы состояние: {current_state}")

    await message.reply(
        "Вы хотите загрузить еще один файл с базой email?",
        reply_markup=get_first_question_keyboard()
    )

        
@router.callback_query(F.data.in_(["load_more_files", "ask_campaign_question"]), StateFilter(EmailProcessingDecisionState.waiting_for_more_files_decision))
async def handle_first_question_decision(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает первый опрос:
    - "Загрузить еще один файл?" -> Ждем загрузку файла.
    - "Нет" -> Переход ко второму вопросу про кампанию.
    """
    current_state = await state.get_state()
    logger.debug(f"📌 Текущее состояние перед обработкой колбэка: {current_state}")
    logger.debug(f"🎯 Получен колбек: {call.data}")

    if call.data == "load_more_files":
        logger.info("🔄 Пользователь выбрал загрузку еще одного файла.")
        await state.set_state(EmailUploadState.waiting_for_file_upload)
        logger.debug(f"✅ Установлено новое состояние: {await state.get_state()}")
        await call.message.edit_text("🔄 Пожалуйста, загрузите новый файл с email-базой.")

    elif call.data == "ask_campaign_question":
        logger.info("🔄 Пользователь отказался загружать файлы. Спрашиваем про кампанию.")
        await state.set_state(EmailProcessingDecisionState.waiting_for_campaign_decision)
        logger.debug(f"✅ Установлено новое состояние: {await state.get_state()}")
        await call.message.edit_text(
            "Вы готовы приступить к созданию рекламной кампании?",
            reply_markup=get_second_question_keyboard()
        )


@router.callback_query(F.data.in_(["proceed_to_campaign", "go_back_to_upload"]), StateFilter(EmailProcessingDecisionState.waiting_for_campaign_decision))
async def handle_second_question_decision(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает второй опрос:
    - "Готов к кампании" -> Завершение.
    - "Нет" -> Возвращение к загрузке файлов + сообщение пользователю.
    """
    current_state = await state.get_state()
    logger.debug(f"📌 Текущее состояние перед обработкой колбэка: {current_state}")
    logger.debug(f"🎯 Получен колбек: {call.data}")

    if call.data == "proceed_to_campaign":
        logger.info("🎯 Пользователь готов к созданию рекламной кампании.")
        await state.clear()
        await handle_add_campaign(call.message, state)

    elif call.data == "go_back_to_upload":
        # ✅ Добавляем сообщение о том, что пользователь может вернуться позже
        await state.clear()
        await call.message.answer("Хорошо, напишите мне, когда будете готовы продолжить. Я всегда на связи.")


async def handle_campaign_decision(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор пользователя: начинать кампанию или вернуться к загрузке файлов.
    """
    logger.debug(f"📌 Текущее состояние перед обработкой кампании: {await state.get_state()}")
    logger.debug(f"🎯 Получен колбек: {call.data}")

    if call.data == "proceed_to_campaign":
        logger.info("🚀 Пользователь выбрал запуск кампании.")
        await state.clear()
        await call.message.edit_text("🚀 Отлично! Теперь давайте создадим рекламную кампанию.")

    elif call.data == "go_back_to_upload":
        logger.info("🔄 Пользователь выбрал вернуться к загрузке файлов.")
        await state.set_state(EmailUploadState.waiting_for_file_upload)
        await call.message.edit_text("🔄 Пожалуйста, загрузите новый файл с email-базой.")

    else:
        await call.answer("❌ Неверный выбор!!!.", show_alert=True)


