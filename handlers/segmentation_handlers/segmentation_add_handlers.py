from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
import logging

from classifier import client
from db.db import SessionLocal
from db.db_segmentation import add_segment_summary, create_segment_table
from db.models import Company
from promts.email_table_promt import EMAIL_SEGMENT_COLUMNS
from promts.segments_promt import SEGMENTATION_PROMPT
from states.states import SegmentationState

logger = logging.getLogger(__name__)
router = Router()


async def handle_create_segment(message: Message, state: FSMContext):
    """
    Хендлер для создания нового сегмента.
    Пользователь отправляет запрос в текстовом формате.
    """
    try:
        # Получаем текст запроса
        user_request = message.text.strip()
        logger.info(f"Получен запрос на создание сегмента: {user_request}")

        # Формируем промпт для модели
        prompt = SEGMENTATION_PROMPT.format(
            user_request=user_request,
            available_filters=", ".join(EMAIL_SEGMENT_COLUMNS)
        )
        logger.debug(f"Промпт для модели: {prompt}")

        # Отправляем промпт в модель и получаем ответ
        model_response = await get_filters_from_model(prompt)
        logger.debug(f"Ответ модели: {model_response}")

        if not model_response:
            await message.reply("Модель не смогла определить параметры сегментации. Проверьте запрос.")
            return

        # Сохраняем фильтры в состояние
        await state.update_data(filters=model_response)
        # Подтверждаем фильтры у пользователя
        await confirm_filters_with_user(message, state)
    except Exception as e:
        logger.error(f"Ошибка при создании сегмента: {e}", exc_info=True)
        await message.reply("Произошла ошибка при создании сегмента.")

async def get_filters_from_model(prompt: str) -> dict:
    """
    Отправляет промпт в модель и возвращает ответ с фильтрами сегментации.

    :param prompt: Сформированный текстовый запрос для модели.
    :return: Словарь с фильтрами сегментации.
    """
    try:
        logger.debug(f"Отправляем запрос в модель: {prompt}")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        filters_raw = response.choices[0].message.content.strip()
        logger.debug(f"Ответ модели (сырой): {filters_raw}")

        import json
        filters = json.loads(filters_raw)
        if "filters" not in filters:
            logger.error(f"Ключ 'filters' отсутствует в ответе модели: {filters}")
            return {}
        return filters["filters"]
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа модели: {e}", exc_info=True)
        return {}


async def confirm_filters_with_user(message: Message, state: FSMContext):
    """
    Подтверждает параметры фильтрации с пользователем.

    :param message: Сообщение пользователя.
    :param state: FSMContext для управления состояниями.
    """
    data = await state.get_data()
    filters = data.get("filters", {})

    await message.reply(
        f"Модель определила следующие фильтры: {filters}\nПодтверждаете? (да/нет)"
    )
    await state.set_state(SegmentationState.waiting_for_confirmation)

@router.message(SegmentationState.waiting_for_confirmation)
async def process_confirmation(message: Message, state: FSMContext):
    """
    Обрабатывает подтверждение фильтров от пользователя.
    """
    user_response = message.text.strip().lower()

    if user_response in ["да", "yes"]:
        data = await state.get_data()
        filters = data.get("filters", {})
        db: Session = SessionLocal()

        try:
            chat_id = message.chat.id
            company = db.query(Company).filter(Company.chat_id == str(chat_id)).first()
            if not company:
                await message.reply("Вы не привязаны к компании. Проверьте настройки.")
                return

            segment_table_name = f"segment_{company.company_id}_{len(company.segments) + 1}"
            create_segment_table(segment_table_name, filters, db)
            add_segment_summary(db, company.company_id, segment_table_name, data.get("user_request"), filters)

            await message.reply(f"Сегмент успешно создан. Имя таблицы: `{segment_table_name}`.")
            logger.info(f"Создан сегмент: {segment_table_name} для компании {company.company_id}.")
        except Exception as e:
            logger.error(f"Ошибка при создании сегмента: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании сегмента.")
        finally:
            db.close()

        await state.clear()
    else:
        await message.reply("Вы отменили создание сегмента.")
        await state.clear()