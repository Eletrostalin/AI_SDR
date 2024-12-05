import json

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session

from classifier import extract_company_data, extract_add_fields
from utils.states import AddCompanyState, BaseState, EditCompanyState
from logger import logger
from db.db import SessionLocal
from utils.utils import process_message
from db.db_company import save_company_info, get_company_info_by_company_id, get_company_by_chat_id, \
    update_company_info, validate_and_merge_company_info, delete_company_info

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

        company_name = company_data.get("company_name")
        if not company_name:
            logger.warning("Название компании не распознано.")
            await state.update_data(company_data=company_data)
            await message.reply("Не удалось определить название компании. Укажите его:")
            await state.set_state(AddCompanyState.waiting_for_company_name)
            return

        await state.update_data(company_data=company_data)
        logger.info(f"Информация о компании успешно извлечена: {company_data}")

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

        await message.reply(
            "Информация о вашей компании:\n"
            "```json\n"
            f"{json.dumps(company_info, indent=4, ensure_ascii=False)}"
            "\n```",
            parse_mode="Markdown"
        )
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
    await state.set_state(EditCompanyState.waiting_for_updated_info)
    logger.debug(f"Состояние установлено: {await state.get_state()}")


@router.message(StateFilter(EditCompanyState.waiting_for_updated_info))
async def process_edit_company_information(message: Message, state: FSMContext, bot):
    """
    Обрабатывает сообщение с информацией для добавления новых данных в компанию.
    """
    try:
        # Извлекаем данные для добавления
        edit_fields = await extract_add_fields(message.text)

        if not edit_fields:
            await message.reply(
                "Не удалось обработать запрос из-за временной недоступности сервиса. Пожалуйста, попробуйте позже."
            )
            logger.error("extract_add_fields вернула None. Возможно, проблема с OpenAI API.")
            await state.set_state(BaseState.default)
            return

        if "error" in edit_fields:
            await message.reply(edit_fields["error"])
            await state.set_state(BaseState.default)
            return

        fields_to_add = edit_fields.get("fields_to_add", {})
        if not fields_to_add:
            await message.reply("Не удалось извлечь данные для добавления. Уточните запрос.")
            await state.set_state(BaseState.default)
            return

        # Проверяем пересечение ключей с существующими данными
        db: Session = SessionLocal()
        try:
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                await message.reply("Компания не найдена.")
                await state.set_state(BaseState.default)
                return

            existing_data = get_company_info_by_company_id(db, company.company_id) or {}
            overlapping_keys = set(fields_to_add.keys()) & set(existing_data.keys())

            if overlapping_keys:
                await message.reply(
                    f"Ошибка: Поля {', '.join(overlapping_keys)} уже существуют. Обновление невозможно."
                )
                await state.set_state(BaseState.default)
                return

            # Объединяем данные
            new_data = {**existing_data, **fields_to_add}
            update_company_info(db, company.company_id, new_data)

            await message.reply("Новая информация успешно добавлена.")
            await state.set_state(BaseState.default)
        except Exception as e:
            logger.error(f"Ошибка при обновлении информации о компании: {e}", exc_info=True)
            await message.reply("Произошла ошибка при добавлении данных компании. Попробуйте снова.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке сообщения. Попробуйте снова.")


@router.message(StateFilter(AddCompanyState.waiting_for_company_name))
async def handle_company_name_confirmation(message: Message, state: FSMContext):
    """
    Уточняет название компании, если оно не распознано из информации пользователя.
    """
    company_name = message.text.strip()
    if not company_name:
        await message.reply("Название компании не может быть пустым. Пожалуйста, введите название снова.")
        return

    state_data = await state.get_data()
    company_data = state_data.get("company_data", {})
    company_data["company_name"] = company_name
    await state.update_data(company_data=company_data)

    description = company_data.get("description", "Описание отсутствует")
    await message.reply(
        f"Название компании: {company_name}\nОписание: {description}\nВсе верно? (да/нет)"
    )
    logger.debug(f"Название компании уточнено: {company_name}. Установлено состояние waiting_for_confirmation.")
    await state.set_state(AddCompanyState.waiting_for_confirmation)


async def handle_delete_company(message: Message, state: FSMContext):
    """
    Обрабатывает запрос на удаление всей информации о компании.
    """
    db = SessionLocal()
    try:
        chat_id = str(message.chat.id)
        company = get_company_by_chat_id(db, chat_id)

        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы добавили данные компании.")
            return

        # Удаляем информацию о компании
        delete_company_info(db, company.company_id)
        await message.reply("Информация о компании успешно удалена.")

        # Возвращаем пользователя в базовое состояние
        await state.set_state(BaseState.default)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка при удалении информации о компании: {e}", exc_info=True)
        await message.reply("Произошла ошибка при удалении информации о компании. Попробуйте снова.")
    finally:
        db.close()