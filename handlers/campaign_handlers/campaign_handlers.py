from aiogram.filters import StateFilter
from admin.ThreadManager import create_thread
from db.db_thread import save_campaign_to_db, save_thread_to_db
from logger import logger
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from promts.campaign_promt import CAMPAIGN_DATA_PROMPT, EMAIL_SEGMENT_COLUMNS
from states.states import AddCampaignState
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.utils import send_to_model

router = Router()


@router.message(StateFilter(None))
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Начало добавления кампании: запрос имени кампании.
    """
    await message.reply("Введите название новой кампании:")
    await state.set_state(AddCampaignState.waiting_for_campaign_name)


@router.message(StateFilter(AddCampaignState.waiting_for_campaign_name))
async def process_campaign_name(message: Message, state: FSMContext):
    """
    Обрабатывает название кампании.
    """
    campaign_name = message.text.strip()
    if not campaign_name:
        await message.reply("Название кампании не может быть пустым. Пожалуйста, введите название ещё раз:")
        return

    await state.update_data(campaign_name=campaign_name)
    await message.reply(
        "Теперь укажите дополнительные данные о кампании: дата начала, дата конца, параметры (например, ЦУ или регион). "
        "Введите данные в любом порядке. Например: 'начало 01.01.2024, конец 31.01.2024, регион Москва'."
    )
    await state.set_state(AddCampaignState.waiting_for_campaign_data)


@router.message(StateFilter(AddCampaignState.waiting_for_campaign_data))
async def process_campaign_data(message: Message, state: FSMContext):
    """
    Обрабатывает данные кампании, отправляя их в модель для анализа.
    """
    user_input = message.text.strip()
    logger.debug(f"Получен ввод данных кампании: {user_input}")

    try:
        # Проверяем наличие необходимых переменных
        logger.debug(f"CAMPAIGN_DATA_PROMPT содержимое: {CAMPAIGN_DATA_PROMPT}")
        logger.debug(f"EMAIL_SEGMENT_COLUMNS содержимое: {EMAIL_SEGMENT_COLUMNS}")

        if not CAMPAIGN_DATA_PROMPT or not isinstance(CAMPAIGN_DATA_PROMPT, str):
            raise ValueError("CAMPAIGN_DATA_PROMPT не определен или имеет неверный тип.")
        if not EMAIL_SEGMENT_COLUMNS or not isinstance(EMAIL_SEGMENT_COLUMNS, list):
            raise ValueError("EMAIL_SEGMENT_COLUMNS не определен или имеет неверный тип.")

        # Формируем запрос для модели
        prompt = CAMPAIGN_DATA_PROMPT.format(user_input=user_input)
        logger.debug(f"Сформированный промт для модели: {prompt}")

        # Отправляем запрос в модель
        response = send_to_model(prompt)
        logger.debug(f"Ответ модели: {response}")

        # Обработка ответа от модели
        import json
        try:
            campaign_data = json.loads(response)
            logger.debug(f"Успешно декодирован JSON: {campaign_data}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON из ответа модели: {e}")
            await message.reply("Ошибка обработки данных. Попробуйте уточнить запрос.")
            return

        # Получение данных состояния
        state_data = await state.get_data()

        # Валидация данных
        campaign_data = validate_model_response(campaign_data, state_data)
        logger.debug(f"Результат валидации: {campaign_data}")

        if not campaign_data:
            logger.error("Валидация завершилась неуспешно.")
            await message.reply("Ошибка в обработке данных. Попробуйте снова.")
            return

        # Проверка на недостающие данные
        missing_fields = []
        if not campaign_data.get("start_date"):
            missing_fields.append("дата начала")
        if not campaign_data.get("end_date"):
            missing_fields.append("дата конца")
        if not campaign_data.get("filters"):
            missing_fields.append("фильтры сегментации")

        if missing_fields:
            logger.debug(f"Недостающие данные: {missing_fields}")
            await state.update_data(campaign_data=campaign_data)
            await message.reply(
                f"Необходимо указать: {', '.join(missing_fields)}. Пожалуйста, уточните недостающие данные."
            )
            if not campaign_data.get("start_date"):
                await state.set_state(AddCampaignState.waiting_for_start_date)
            elif not campaign_data.get("end_date"):
                await state.set_state(AddCampaignState.waiting_for_end_date)
            elif not campaign_data.get("filters"):
                await state.set_state(AddCampaignState.waiting_for_filters)
            return

        # Если все данные собраны
        logger.debug("Все данные успешно собраны. Обновляем состояние.")
        await state.update_data(campaign_data=campaign_data)
        await message.reply(
            f"Проверьте данные кампании:\n"
            f"Название: {campaign_data.get('campaign_name')}\n"
            f"Дата начала: {campaign_data['start_date']}\n"
            f"Дата конца: {campaign_data['end_date']}\n"
            f"Фильтры: {campaign_data['filters']}\n"
            f"Параметры: {campaign_data.get('params')}\n\n"
            "Введите 'да' для подтверждения или 'нет' для отмены."
        )
        await state.set_state(AddCampaignState.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка обработки данных кампании: {e}")
        await message.reply("Произошла ошибка при обработке данных. Попробуйте снова.")


@router.message(StateFilter(AddCampaignState.waiting_for_start_date))
async def process_start_date(message: Message, state: FSMContext):
    """
    Обрабатывает дату начала кампании.
    """
    start_date = message.text.strip()
    try:
        from datetime import datetime
        datetime.strptime(start_date, "%d.%m.%Y")

        campaign_data = await state.get_data("campaign_data")
        campaign_data["start_date"] = start_date
        await state.update_data(campaign_data=campaign_data)

        # Проверяем, есть ли дата окончания
        if not campaign_data.get("end_date"):
            await message.reply("Укажите дату окончания кампании (в формате ДД.ММ.ГГГГ):")
            await state.set_state(AddCampaignState.waiting_for_end_date)
        else:
            await confirm_campaign(message, state)

    except ValueError:
        await message.reply("Некорректный формат даты. Укажите дату начала в формате ДД.ММ.ГГГГ.")


@router.message(StateFilter(AddCampaignState.waiting_for_end_date))
async def process_end_date(message: Message, state: FSMContext):
    """
    Обрабатывает дату окончания кампании.
    """
    end_date = message.text.strip()
    try:
        from datetime import datetime
        datetime.strptime(end_date, "%d.%m.%Y")

        campaign_data = await state.get_data("campaign_data")
        campaign_data["end_date"] = end_date
        await state.update_data(campaign_data=campaign_data)

        # Переходим к подтверждению
        await confirm_campaign(message, state)

    except ValueError:
        await message.reply("Некорректный формат даты. Укажите дату окончания в формате ДД.ММ.ГГГГ.")

@router.message(StateFilter(AddCampaignState.waiting_for_filters))
async def process_filters(message: Message, state: FSMContext):
    """
    Обрабатывает ввод фильтров сегментации.
    """
    user_input = message.text.strip()
    try:
        # Получаем текущие данные состояния
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})

        # Проверяем корректность ввода фильтров
        filters = {}
        for pair in user_input.split(","):
            if ":" not in pair:
                await message.reply(
                    "Некорректный формат фильтра. Используйте формат 'ключ: значение'. Например: 'region: Москва'."
                )
                return
            key, value = map(str.strip, pair.split(":", 1))
            if key not in EMAIL_SEGMENT_COLUMNS:
                await message.reply(
                    f"Недопустимый ключ фильтра '{key}'. Допустимые ключи: {', '.join(EMAIL_SEGMENT_COLUMNS)}."
                )
                return
            filters[key] = value

        # Сохраняем фильтры в состоянии
        campaign_data["filters"] = filters
        await state.update_data(campaign_data=campaign_data)

        # Проверяем, все ли данные собраны
        if campaign_data.get("start_date") and campaign_data.get("end_date"):
            # Если все данные есть, переходим к подтверждению
            await message.reply(
                f"Проверьте данные кампании:\n"
                f"Название: {campaign_data.get('campaign_name')}\n"
                f"Дата начала: {campaign_data['start_date']}\n"
                f"Дата конца: {campaign_data['end_date']}\n"
                f"Фильтры: {campaign_data.get('filters')}\n"
                f"Параметры: {campaign_data.get('params', {})}\n\n"
                "Введите 'да' для подтверждения или 'нет' для отмены."
            )
            await state.set_state(AddCampaignState.waiting_for_confirmation)
        else:
            # Если даты отсутствуют, возвращаемся к их уточнению
            if not campaign_data.get("start_date"):
                await message.reply("Укажите дату начала кампании (в формате ДД.ММ.ГГГГ):")
                await state.set_state(AddCampaignState.waiting_for_start_date)
            elif not campaign_data.get("end_date"):
                await message.reply("Укажите дату окончания кампании (в формате ДД.ММ.ГГГГ):")
                await state.set_state(AddCampaignState.waiting_for_end_date)

    except Exception as e:
        logger.error(f"Ошибка обработки фильтров: {e}")
        await message.reply("Произошла ошибка при обработке фильтров. Попробуйте снова.")


@router.message(StateFilter(AddCampaignState.waiting_for_missing_data))
async def process_missing_data(message: Message, state: FSMContext):
    """
    Обрабатывает недостающие данные (например, дату начала или окончания кампании).
    """
    user_input = message.text.strip()
    try:
        # Получаем текущие данные состояния
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})

        # Проверяем, какое поле требуется заполнить
        if "start_date" not in campaign_data or not campaign_data.get("start_date"):
            from datetime import datetime
            try:
                # Проверяем корректность введенной даты
                start_date = datetime.strptime(user_input, "%d.%m.%Y")
                campaign_data["start_date"] = user_input
                await state.update_data(campaign_data=campaign_data)
                # Переходим к следующему шагу
                if not campaign_data.get("end_date"):
                    await message.reply("Укажите дату окончания кампании (в формате ДД.ММ.ГГГГ):")
                    return
            except ValueError:
                await message.reply("Некорректный формат даты. Укажите дату начала в формате ДД.ММ.ГГГГ.")
                return

        if "end_date" not in campaign_data or not campaign_data.get("end_date"):
            from datetime import datetime
            try:
                # Проверяем корректность введенной даты
                end_date = datetime.strptime(user_input, "%d.%m.%Y")
                campaign_data["end_date"] = user_input
                await state.update_data(campaign_data=campaign_data)
            except ValueError:
                await message.reply("Некорректный формат даты. Укажите дату окончания в формате ДД.ММ.ГГГГ.")
                return

        # Проверяем, все ли данные заполнены
        if campaign_data.get("start_date") and campaign_data.get("end_date"):
            await state.update_data(campaign_data=campaign_data)
            await message.reply(
                f"Проверьте данные кампании:\n"
                f"Название: {campaign_data.get('campaign_name')}\n"
                f"Дата начала: {campaign_data['start_date']}\n"
                f"Дата окончания: {campaign_data['end_date']}\n"
                f"Параметры: {campaign_data.get('params', {})}\n\n"
                "Введите 'да' для подтверждения или 'нет' для отмены."
            )
            await state.set_state(AddCampaignState.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка обработки недостающих данных: {e}")
        await message.reply("Произошла ошибка. Попробуйте ещё раз.")


async def confirm_campaign(message: Message, state: FSMContext):
    """
    Подтверждает собранные данные кампании.
    """
    campaign_data = await state.get_data("campaign_data")
    await message.reply(
        f"Проверьте данные кампании:\n"
        f"Название: {campaign_data.get('campaign_name')}\n"
        f"Дата начала: {campaign_data.get('start_date')}\n"
        f"Дата конца: {campaign_data.get('end_date')}\n"
        f"Параметры: {campaign_data.get('params')}\n\n"
        "Введите 'да' для подтверждения или 'нет' для отмены."
    )
    await state.set_state(AddCampaignState.waiting_for_confirmation)


@router.message(StateFilter(AddCampaignState.waiting_for_confirmation))
async def confirm_campaign_creation(message: Message, state: FSMContext):
    """
    Завершает создание кампании и сохраняет данные в базе.
    """
    if message.text.strip().lower() not in ["да", "нет"]:
        await message.reply("Введите 'да' для подтверждения или 'нет' для отмены.")
        return

    if message.text.strip().lower() == "да":
        db = SessionLocal()
        try:
            campaign_data = await state.get_data("campaign_data")
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)

            if not company:
                await message.reply("Компания не найдена. Добавьте её перед созданием кампании.")
                return

            # Создаём тему и сохраняем кампанию
            bot = message.bot
            thread_name = f"Кампания: {campaign_data['campaign_name']}"
            thread_id = await create_thread(bot, chat_id, thread_name)

            save_thread_to_db(db, chat_id, thread_id, thread_name)
            save_campaign_to_db(db, company.company_id, campaign_data)

            await message.reply(f"Кампания '{campaign_data['campaign_name']}' успешно создана.")
            await state.clear()
        except Exception as e:
            logger.error(f"Ошибка создания кампании: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании кампании.")
        finally:
            db.close()
    else:
        await message.reply("Создание кампании отменено.")
        await state.clear()


def validate_model_response(response: dict, state_data: dict) -> dict:
    """
    Проверяет и нормализует ответ модели, добавляя имя кампании из состояния.

    :param response: Ответ модели (предполагается словарь).
    :param state_data: Данные состояния FSM.
    :return: Словарь с проверенными данными.
    """
    try:
        logger.debug(f"Начало валидации ответа модели: {response}")

        # Инициализируем структуру данных
        campaign_data = {
            "campaign_name": state_data.get("campaign_name") or response.get("campaign_name", "").strip() or None,
            "start_date": response.get("start_date", "").strip(),
            "end_date": response.get("end_date", "").strip(),
            "filters": response.get("filters", {}),
            "params": response.get("params", {}),
        }

        # Проверяем формат дат
        from datetime import datetime
        if campaign_data["start_date"]:
            logger.debug(f"Проверка даты начала: {campaign_data['start_date']}")
            campaign_data["start_date"] = datetime.strptime(
                campaign_data["start_date"], "%d.%m.%Y"
            ).strftime("%d.%m.%Y")
        if campaign_data["end_date"]:
            logger.debug(f"Проверка даты окончания: {campaign_data['end_date']}")
            campaign_data["end_date"] = datetime.strptime(
                campaign_data["end_date"], "%d.%m.%Y"
            ).strftime("%d.%m.%Y")

        # Убедимся, что "filters" и "params" являются словарями
        if not isinstance(campaign_data["filters"], dict):
            logger.warning(f"Поле 'filters' не является словарем: {campaign_data['filters']}")
            campaign_data["filters"] = {}
        if not isinstance(campaign_data["params"], dict):
            logger.warning(f"Поле 'params' не является словарем: {campaign_data['params']}")
            campaign_data["params"] = {}

        logger.debug(f"Результат валидации: {campaign_data}")
        return campaign_data
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Ошибка валидации ответа модели: {e}", exc_info=True)
        logger.debug(f"Ошибка в данных: {response}")
        return {}