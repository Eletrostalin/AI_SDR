import json

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from sqlalchemy.orm import Session

from classifier import extract_company_data, client
from db.models import CompanyInfo
from promts.company_promt import generate_edit_company_prompt
from states.states import AddCompanyState, BaseState, EditCompanyState
from logger import logger
from db.db import SessionLocal
from utils.utils import process_message
from db.db_company import (save_company_info,
                           get_company_info_by_company_id,
                           get_company_by_chat_id,
                           delete_additional_info)

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
async def handle_view_company(message: Message, state: FSMContext):
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
        await state.clear()
        logger.debug(f"Информация о компании отправлена пользователю: {company_info}")

    except Exception as e:
        logger.error(f"Ошибка отображения информации о компании: {e}", exc_info=True)
        await message.reply(f"Ошибка при извлечении данных: {str(e)}")
    finally:
        db.close()


@router.message()
async def handle_edit_company(message: Message, state: FSMContext):
    """
    Инициирует процесс редактирования информации о компании.
    """
    db: Session = SessionLocal()
    try:
        chat_id = str(message.chat.id)
        company = get_company_by_chat_id(db, chat_id)

        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы добавили данные компании.")
            return

        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()

        if not company_info:
            await message.reply("Информация о компании отсутствует.")
            return

        await state.update_data(current_info=company_info.additional_info or "")
        await message.reply(
            "Что вы хотите изменить в информации о компании? Опишите ваши изменения."
        )
        await state.set_state(EditCompanyState.waiting_for_updated_info)
    except Exception as e:
        logger.error(f"Ошибка при инициализации редактирования компании: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()

@router.message(StateFilter(EditCompanyState.waiting_for_updated_info))
async def process_edit_company_information(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с новой информацией для редактирования данных компании.
    """
    db: Session = SessionLocal()
    try:
        chat_id = str(message.chat.id)
        company = get_company_by_chat_id(db, chat_id)

        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы добавили данные компании.")
            await state.set_state(BaseState.default)
            return

        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()

        if not company_info:
            await message.reply("Информация о компании отсутствует.")
            await state.set_state(BaseState.default)
            return

        # Извлекаем текущую информацию о компании
        current_info = {
            "company_name": company_info.company_name,
            "industry": company_info.industry,
            "description": company_info.additional_info or "Не указано",
        }
        new_info = message.text.strip()

        # Генерируем промт и отправляем запрос к модели
        prompt = generate_edit_company_prompt(current_info, new_info)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        updated_info = response.choices[0].message.content.strip()
        logger.debug(f"Обновленная информация от модели: {updated_info}")

        # Сохраняем обновленные данные для подтверждения
        await state.update_data(updated_info=updated_info)

        # Отправляем пользователю результат на подтверждение
        await message.reply(
            f"Вот обновленная информация о компании:\n\n{updated_info}\n\n"
            f"Вы подтверждаете изменения? Напишите 'да' для сохранения или 'нет' для повторного редактирования."
        )
        await state.set_state(EditCompanyState.waiting_for_confirmation)
    except Exception as e:
        logger.error(f"Ошибка при обработке изменений компании: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке ваших данных. Попробуйте снова.")
    finally:
        db.close()

@router.message(StateFilter(EditCompanyState.waiting_for_confirmation))
async def confirm_edit_company_information(message: Message, state: FSMContext):
    """
    Обрабатывает подтверждение обновления информации о компании.
    """
    db: Session = SessionLocal()
    try:
        if message.text.lower() == "да":
            # Сохраняем подтвержденные изменения
            state_data = await state.get_data()
            updated_info = state_data.get("updated_info")

            if not updated_info:
                await message.reply("Нет данных для обновления. Начните процесс заново.")
                await state.set_state(BaseState.default)
                return

            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                await message.reply("Компания не найдена.")
                await state.set_state(BaseState.default)
                return

            # Сохраняем только значение в поле `additional_info`
            company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()
            company_info.additional_info = updated_info  # Здесь уже сохранится только значение строки
            db.commit()

            await message.reply("Изменения успешно сохранены.")
            await state.clear()
        elif message.text.lower() == "нет":
            await message.reply("Отправьте новую информацию для редактирования.")
            await state.set_state(EditCompanyState.waiting_for_updated_info)
        else:
            await message.reply("Пожалуйста, напишите 'да' для сохранения или 'нет' для редактирования.")
    except Exception as e:
        logger.error(f"Ошибка при подтверждении изменений компании: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке подтверждения. Попробуйте снова.")
    finally:
        db.close()

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