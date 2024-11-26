from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from classifier import extract_company_data
from utils.states import AddCompanyState, BaseState, EditCompanyState
from logger import logger
from db.db import SessionLocal
from db.models import Company
from utils.utils import process_message
from db.db_company import save_company_info, get_company_info_by_company_id, get_company_by_chat_id, update_company_info

router = Router()


# Обработчик начала добавления компании
async def handle_add_company(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления информации о компании.
    """
    logger.debug("Инициация добавления компании. Установка состояния waiting_for_information.")
    await message.reply("Пожалуйста, отправьте информацию о вашей компании (текст, файл или ссылку).")
    await state.set_state(AddCompanyState.waiting_for_information)


@router.message(StateFilter(AddCompanyState.waiting_for_information))
async def process_company_information(message: Message, state: FSMContext, bot):
    """
    Обрабатывает сообщение с информацией о компании, отправляет данные модели
    для формирования JSON, и сохраняет данные в таблицу CompanyInfo.
    """
    logger.debug("Получено сообщение для обработки информации о компании.")
    extracted_info = await process_message(message, bot)

    if extracted_info["type"] == "error":
        logger.warning(f"Ошибка извлечения информации из сообщения: {extracted_info['message']}")
        await message.reply(f"Ошибка: {extracted_info['message']}")
        return

    try:
        logger.debug("Передача данных в OpenAI для извлечения информации о компании.")
        company_data = extract_company_data(extracted_info['content'])

        if not isinstance(company_data, dict):
            raise ValueError("Получены некорректные данные от модели. Ожидается JSON.")

        await state.update_data(company_data=company_data)
        logger.info(f"Информация о компании успешно извлечена: {company_data}")

        company_name = company_data.get("company_name", "Название компании неСontentьно")
        description = company_data.get("description", "Описание отсутствует")
        await message.reply(
            f"Мы интерпретировали вашу информацию следующим образом:\nКомпания: {company_name}\nОписание: {description}\nВсе верно? (да/нет)"
        )
        logger.debug("Отправлено сообщение для подтверждения данных о компании.")
        await state.set_state(AddCompanyState.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка обработки информации о компании: {e}", exc_info=True)
        await message.reply(f"Ошибка при обработке информации: {str(e)}")


@router.message(StateFilter(AddCompanyState.waiting_for_confirmation))
async def confirm_company_information(message: Message, state: FSMContext):
    """
    Подтверждает или отклоняет интерпретированную информацию.
    """
    logger.debug("Получено подтверждение информации о компании.")
    if message.text.lower() in ["да", "верно"]:
        state_data = await state.get_data()
        company_data = state_data.get("company_data")

        db = SessionLocal()
        try:
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                logger.warning(f"Компания с chat_id {chat_id} не найдена в базе.")
                await message.reply("Ошибка: Компания не найдена. Попробуйте снова.")
                await state.clear()
                return

            save_company_info(db, company_id=company.company_id, details=company_data)
            logger.info(f"Информация о компании сохранена: {company_data}")
            await message.reply("Информация о компании успешно сохранена!")
            await state.set_state(BaseState.default)

        except Exception as e:
            logger.error(f"Ошибка сохранения информации о компании: {e}", exc_info=True)
            await message.reply(f"Ошибка при сохранении данных: {str(e)}")
        finally:
            db.close()
    else:
        logger.debug("Пользователь отклонил информацию о компании.")
        await message.reply(
            "Уточнение информации пока в разработке. Вы возвращены в базовое состояние. Попробуйте снова."
        )
        await state.clear()


@router.message()
async def handle_view_company(message: Message):
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

        await message.reply(f"Информация о вашей компании:\n```json\n{company_info}\n```", parse_mode="Markdown")
        logger.debug(f"Информация о компании отправлена пользователю: {company_info}")

    except Exception as e:
        logger.error(f"Ошибка отображения информации о компании: {e}", exc_info=True)
        await message.reply(f"Ошибка при извлечении данных: {str(e)}")
    finally:
        db.close()


async def handle_edit_company(message: Message, state: FSMContext):
    """
    Инициирует процесс редактирования информации о компании.
    """
    await message.reply("Пожалуйста, отправьте новую информацию для обновления данных о компании.")
    await state.set_state("edit_company_info")


@router.message(StateFilter(EditCompanyState.waiting_for_updated_info))
async def process_edit_company_information(message: Message, state: FSMContext, bot):
    """
    Обрабатывает сообщение с обновленной информацией о компании и обновляет данные в базе.
    """
    try:
        # Обработка сообщения
        extracted_info = await process_message(message, bot)

        if extracted_info["type"] == "error":
            await message.reply(f"Ошибка: {extracted_info['message']}")
            return

        # Обновляем информацию через OpenAI или другим способом
        new_details = await extract_company_data(extracted_info['content'])

        if not isinstance(new_details, dict):
            raise ValueError("Получены некорректные данные от модели. Ожидается JSON.")

        # Открываем сессию для работы с базой данных
        db: Session = SessionLocal()
        try:
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                await message.reply("Компания не найдена.")
                return

            # Обновляем данные компании
            update_company_info(db, company.company_id, new_details)
            await message.reply("Информация о компании успешно обновлена.")
            await state.set_state(BaseState.default)

        except Exception as e:
            logger.error(f"Ошибка при обновлении информации о компании: {e}", exc_info=True)
            await message.reply("Произошла ошибка при обновлении данных компании. Попробуйте снова.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке сообщения. Попробуйте снова.")