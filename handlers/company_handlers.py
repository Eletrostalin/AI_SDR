from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from db.db import SessionLocal
from langchain_helper import LangChainHelper

from procesed_message import process_message
from utils.company_utils import save_company_info, get_company_by_telegram_id
from utils.states import AddCompanyState

# Инициализация LangChainHelper
langchain_helper = LangChainHelper(api_key="YOUR_OPENAI_API_KEY")


# 1. Обработчик добавления компании
async def handle_add_company(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления информации о компании.
    """
    await message.reply("Пожалуйста, отправьте информацию о вашей компании (текст, файл или ссылку).")
    await state.set_state(AddCompanyState.waiting_for_information)


# 2. Обработчик получения информации
async def process_company_information(message: Message, state: FSMContext, bot):
    """
    Обрабатывает сообщение с информацией о компании, отправляет данные модели
    для формирования JSON.
    """
    # Извлечение информации из сообщения
    extracted_info = await process_message(message, bot)

    if extracted_info["type"] == "error":
        await message.reply(f"Ошибка: {extracted_info['message']}")
        return

    # Формируем текст для передачи модели
    prompt = f"""
    Извлеки данные о компании из следующей информации:
    {extracted_info['content']}
    Верни их в формате JSON:
    {{
        "company_name": "Название компании",
        "industry": "Сфера деятельности",
        "location": "Местоположение",
        "description": "Описание"
    }}
    """

    try:
        # Получаем JSON с данными о компании через LangChain
        company_data = await langchain_helper.classify_request(prompt)
        await state.update_data(company_data=company_data)

        # Запрашиваем подтверждение у пользователя
        await message.reply(
            f"Мы интерпретировали вашу информацию следующим образом:\n{company_data}\nВсе верно? (да/нет)"
        )
        await state.set_state(AddCompanyState.waiting_for_confirmation)
    except Exception as e:
        await message.reply(f"Ошибка при обработке информации: {str(e)}")


# 3. Обработчик подтверждения
async def confirm_company_information(message: Message, state: FSMContext):
    """
    Подтверждает или отклоняет интерпретированную информацию.
    """
    if message.text.lower() in ["да", "верно"]:
        # Получаем данные из состояния
        state_data = await state.get_data()
        company_data = state_data.get("company_data")

        # Сохраняем данные в базу
        db = SessionLocal()
        try:
            user_company = get_company_by_telegram_id(db, telegram_id=str(message.from_user.id))
            save_company_info(db, company_id=user_company.company_id, details=company_data)
        except Exception as e:
            await message.reply(f"Ошибка при сохранении данных: {str(e)}")
        finally:
            db.close()

        await message.reply("Информация о компании успешно сохранена!")
        await state.clear()
    else:
        # Очищаем ранее сохранённые данные
        await state.update_data(company_data=None)
        await message.reply("Отправьте информацию заново.")
        await state.set_state(AddCompanyState.waiting_for_information)


# 4. Обработчик просмотра компании
async def handle_view_company(message: Message):
    """
    Отображает информацию о компании пользователя.
    """
    db = SessionLocal()
    try:
        user_company = get_company_by_telegram_id(db, telegram_id=str(message.from_user.id))
        if user_company and user_company.info:
            company_info = user_company.info[0]  # Предполагаем, что у компании одна запись info
            await message.reply(f"Информация о вашей компании:\n{company_info.details}")
        else:
            await message.reply("Информация о компании отсутствует. Добавьте её командой /add_company.")
    except Exception as e:
        await message.reply(f"Ошибка при извлечении данных: {str(e)}")
    finally:
        db.close()