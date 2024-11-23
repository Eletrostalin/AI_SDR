from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import OPENAI_API_KEY
from db.db import SessionLocal
from db.models import Company
from langchain_helper import LangChainHelper
from procesed_message import process_message
from db.db_company import save_company_info, get_company_by_telegram_id
from utils.states import AddCompanyState

# Инициализация LangChainHelper
langchain_helper = LangChainHelper(api_key=OPENAI_API_KEY)
router = Router()

# 1. Обработчик добавления компании
async def handle_add_company(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления информации о компании.
    """
    await message.reply("Пожалуйста, отправьте информацию о вашей компании (текст, файл или ссылку).")
    await state.set_state(AddCompanyState.waiting_for_information)


@router.message(StateFilter(AddCompanyState.waiting_for_information))
async def process_company_information(message: Message, state: FSMContext, bot):
    """
    Обрабатывает сообщение с информацией о компании, отправляет данные модели
    для формирования JSON, и сохраняет данные в таблицу CompanyInfo.
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
    Сгенерируй и отдай JSON следующего вида. Ты можешь добавлять в ответ дополнительные значения, если они присутствуют:
    {{
        "company_name": "Название компании",
        "industry": "Сфера деятельности",
        "description": "Описание"
    }}
    """

    try:
        # Получаем JSON с данными о компании через LangChain
        company_data = await langchain_helper.classify_request(prompt)
        await state.update_data(company_data=company_data)

        # Формируем строку для пользователя
        company_name = company_data.get("company_name", "Название компании не определено")
        description = company_data.get("description", "Описание отсутствует")
        await message.reply(
            f"Мы интерпретировали вашу информацию следующим образом:\nКомпания: {company_name}\nОписание: {description}\nВсе верно? (да/нет)"
        )
        await state.set_state(AddCompanyState.waiting_for_confirmation)

    except Exception as e:
        await message.reply(f"Ошибка при обработке информации: {str(e)}")


@router.message(StateFilter(AddCompanyState.waiting_for_confirmation))
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
            # Проверяем наличие компании в базе по chat_id
            chat_id = str(message.chat.id)
            company = db.query(Company).filter_by(chat_id=chat_id).first()

            if not company:
                # Если компания не найдена, отправляем сообщение
                await message.reply("Ошибка: Компания не найдена. Попробуйте снова.")
                await state.clear()
                return

            # Сохраняем информацию о компании в CompanyInfo
            save_company_info(db, company_id=company.company_id, details=company_data)

            await message.reply("Информация о компании успешно сохранена!")
            await state.clear()

        except Exception as e:
            await message.reply(f"Ошибка при сохранении данных: {str(e)}")
        finally:
            db.close()

    else:
        # Если пользователь говорит "нет", возвращаем в базовое состояние
        await message.reply(
            "Уточнение информации пока в разработке. Вы возвращены в базовое состояние. Попробуйте снова."
        )
        await state.clear()


@router.message()
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