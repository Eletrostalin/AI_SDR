from aiogram.filters import StateFilter

from admin.ThreadManager import create_thread
from db.db_thread import save_campaign_to_db, save_thread_to_db
from logger import logger
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from states.states import AddCampaignState, BaseState
from classifier import extract_campaign_data_with_validation
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.utils import process_message

router = Router()

# Обработчик начала добавления кампании
@router.message(StateFilter(None))
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления кампании.
    """
    await message.reply("Введите название кампании или отправьте полную информацию о кампании.")
    await state.set_state(AddCampaignState.waiting_for_campaign_name)


# Обработчик сообщения с названием кампании
@router.message(StateFilter(AddCampaignState.waiting_for_campaign_name))
async def process_campaign_name(message: Message, state: FSMContext):
    """
    Обрабатывает название кампании или сообщение с полной информацией.
    """
    logger.debug(f"Получено сообщение: {message.text}, текущее состояние: {await state.get_state()}")

    campaign_name = message.text.strip()
    logger.debug(f"Обработанное название кампании: {campaign_name}")

    if campaign_name:
        try:
            logger.debug("Проверка, является ли сообщение полным текстом с данными кампании.")
            extracted_info = await process_message(message, message.bot)
            logger.debug(f"Извлеченная информация из сообщения: {extracted_info}")

            if extracted_info["type"] == "text":  # Проверяем, что это текстовая информация
                logger.debug("Сообщение распознано как текстовая информация. Передача данных на валидацию.")
                campaign_data = await extract_campaign_data_with_validation(extracted_info['content'], state, message)
                logger.debug(f"Результаты валидации данных кампании: {campaign_data}")

                if campaign_data:
                    logger.debug("Полные данные кампании успешно извлечены. Передача в обработчик.")
                    await handle_full_campaign_data(campaign_data, state, message)
                    return
                else:
                    # Проверяем, если были частичные данные
                    partial_data = await state.get_data()
                    if partial_data.get("partial_campaign_data"):
                        logger.debug("Обнаружены частичные данные кампании.")
                        return

        except Exception as e:
            logger.error(f"Ошибка при обработке текста кампании: {e}")
            await message.reply(f"Произошла ошибка при обработке данных кампании: {e}")
            return

        # Если это только название кампании
        logger.debug("Сохранение названия кампании и запрос даты начала.")
        await state.update_data(campaign_name=campaign_name)
        await message.reply("Введите дату начала кампании (в формате ДД.ММ.ГГГГ):")
        await state.set_state(AddCampaignState.waiting_for_start_date)
    else:
        logger.warning("Получено пустое название кампании.")
        await message.reply("Название кампании не может быть пустым. Укажите название ещё раз.")


async def handle_full_campaign_data(campaign_data: dict, state: FSMContext, message: Message):
    """
    Обрабатывает полный JSON с данными кампании.
    """
    logger.debug("handle_full_campaign_data: Начало обработки данных кампании.")
    logger.debug(f"handle_full_campaign_data: Полученные данные кампании: {campaign_data}")

    # Обязательные поля
    required_fields = ["campaign_name", "start_date", "end_date"]
    # Проверяем, какие поля отсутствуют
    missing_fields = [field for field in required_fields if not campaign_data.get(field)]
    logger.debug(f"handle_full_campaign_data: Отсутствующие поля: {missing_fields}" if missing_fields else "handle_full_campaign_data: Все обязательные поля присутствуют.")

    if not missing_fields:
        # Все данные есть, сохраняем и запрашиваем подтверждение
        logger.info("handle_full_campaign_data: Все данные кампании собраны. Сохраняем состояние и запрашиваем подтверждение.")
        await state.update_data(campaign_data=campaign_data)
        logger.debug(f"handle_full_campaign_data: Данные кампании успешно сохранены в состояние: {await state.get_data()}")

        # Устанавливаем состояние для подтверждения
        await state.set_state(AddCampaignState.waiting_for_confirmation)
        logger.debug("handle_full_campaign_data: Состояние установлено на waiting_for_confirmation.")

        # Отправляем пользователю запрос на подтверждение
        await message.reply(
            f"Пожалуйста, подтвердите создание кампании:\n\n"
            f"Название: {campaign_data['campaign_name']}\n"
            f"Дата начала: {campaign_data['start_date']}\n"
            f"Дата окончания: {campaign_data['end_date']}\n"
            f"Параметры: {campaign_data.get('params', {})}\n\n"
            f"Введите 'да' для подтверждения или 'нет' для отмены."
        )
    else:
        # Если данных не хватает, сохраняем частично и запрашиваем недостающие
        logger.warning(f"handle_full_campaign_data: Данные кампании неполные. Пользователю нужно дополнить: {missing_fields}")
        await state.update_data(campaign_data=campaign_data)

        # Последовательно проверяем и запрашиваем недостающие данные
        if "campaign_name" in missing_fields:
            await state.set_state(AddCampaignState.waiting_for_campaign_name)
            await message.reply("Название кампании отсутствует. Укажите его:")
            logger.debug("handle_full_campaign_data: Состояние установлено на waiting_for_campaign_name.")
        elif "start_date" in missing_fields:
            await state.set_state(AddCampaignState.waiting_for_start_date)
            await message.reply("Дата начала кампании отсутствует. Укажите ее в формате ДД.ММ.ГГГГ:")
            logger.debug("handle_full_campaign_data: Состояние установлено на waiting_for_start_date.")
        elif "end_date" in missing_fields:
            await state.set_state(AddCampaignState.waiting_for_end_date)
            await message.reply("Дата окончания кампании отсутствует. Укажите ее в формате ДД.ММ.ГГГГ:")
            logger.debug("handle_full_campaign_data: Состояние установлено на waiting_for_end_date.")


# Обработка даты начала кампании
@router.message(StateFilter(AddCampaignState.waiting_for_start_date))
async def process_start_date(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с датой начала кампании.
    """
    start_date_str = message.text.strip()
    from datetime import datetime

    try:
        # Попробуем преобразовать дату в объект datetime
        start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
        logger.debug(f"Дата начала кампании успешно преобразована: {start_date}")

        # Сохраняем дату начала в данные состояния
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        campaign_data["start_date"] = start_date_str
        await state.update_data(campaign_data=campaign_data)

        # Переходим к следующему шагу
        await message.reply("Введите дату окончания кампании (в формате ДД.ММ.ГГГГ):")
        await state.set_state(AddCampaignState.waiting_for_end_date)

    except ValueError:
        # Если дата не распознается, отправляем сообщение об ошибке
        logger.warning(f"Некорректный формат даты начала кампании: {start_date_str}")
        await message.reply("Некорректный формат даты. Укажите дату начала в формате ДД.ММ.ГГГГ.")


@router.message(StateFilter(AddCampaignState.waiting_for_end_date))
async def process_end_date(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с датой окончания кампании.
    """
    end_date = message.text.strip()
    try:
        from datetime import datetime
        # Проверяем формат ДД.ММ.ГГГГ
        datetime.strptime(end_date, "%d.%m.%Y")

        # Сохраняем дату окончания в данные состояния
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        campaign_data["end_date"] = end_date
        await state.update_data(campaign_data=campaign_data)

        logger.debug(f"Дата окончания кампании обновлена: {end_date}")

        # Генерация подтверждающего сообщения
        confirmation_message = (
            "Все данные собраны. Проверьте информацию:\n"
            f"Название: {campaign_data.get('campaign_name', 'Не указано')}\n"
            f"Дата начала: {campaign_data.get('start_date', 'Не указано')}\n"
            f"Дата окончания: {campaign_data.get('end_date', 'Не указано')}\n"
        )

        # Проверяем наличие параметров
        params = campaign_data.get('params', {})
        if params:
            params_str = "\n".join([f"{k}: {v}" for k, v in params.items()])
            confirmation_message += f"Параметры:\n{params_str}\n"

        confirmation_message += "Все верно? (да/нет)"

        # Переключаем состояние на ожидание подтверждения
        await message.reply(confirmation_message)
        await state.set_state(AddCampaignState.waiting_for_confirmation)

    except ValueError:
        await message.reply("Некорректный формат даты. Укажите дату окончания в формате ДД.ММ.ГГГГ.")



@router.message(StateFilter(AddCampaignState.waiting_for_params))
async def process_campaign_params(message: Message, state: FSMContext):
    """
    Обрабатывает параметры кампании.
    """
    text = message.text.strip()
    if text.lower() == "готово":
        # Завершаем ввод параметров и показываем подтверждение
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        campaign_name = campaign_data.get("campaign_name", "Не указано")
        start_date = campaign_data.get("start_date", "Не указано")
        end_date = campaign_data.get("end_date", "Не указано")
        params = campaign_data.get("params", {})
        params_str = "\n".join([f"{k}: {v}" for k, v in params.items()]) if params else "Нет параметров"

        await message.reply(
            f"Проверьте данные вашей кампании:\n"
            f"Название: {campaign_name}\n"
            f"Дата начала: {start_date}\n"
            f"Дата окончания: {end_date}\n"
            f"Параметры:\n{params_str}\n"
            f"Все верно? (да/нет)"
        )
        await state.set_state(AddCampaignState.waiting_for_confirmation)
    else:
        # Добавляем параметр в состояние
        if ":" not in text:
            await message.reply("Некорректный формат параметра. Используйте формат 'ключ: значение'.")
            return

        key, value = map(str.strip, text.split(":", 1))
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        params = campaign_data.get("params", {})
        params[key] = value
        campaign_data["params"] = params
        await state.update_data(campaign_data=campaign_data)

        # Сразу запрашиваем следующую строку
        await message.reply("Параметр добавлен. Укажите следующий параметр или напишите 'готово', чтобы продолжить.")


@router.message(StateFilter(AddCampaignState.waiting_for_confirmation))
async def confirm_campaign_creation(message: Message, state: FSMContext):
    """
    Подтверждает добавление кампании в базу данных, создает тему в чате и инициирует создание контентного плана.
    """
    logger.debug(f"Подтверждение кампании. Сообщение: {message.text}. Текущее состояние: {await state.get_state()}")

    db = None
    if message.text.lower() in ["да", "верно"]:
        try:
            # Получаем данные из состояния
            state_data = await state.get_data()
            campaign_data = state_data.get("campaign_data", {})

            if not campaign_data:
                logger.error("Данные кампании отсутствуют.")
                await message.reply("Ошибка: данные кампании не найдены. Попробуйте создать кампанию заново.")
                await state.set_state(AddCampaignState.waiting_for_campaign_name)
                return

            campaign_name = campaign_data.get("campaign_name")
            start_date = campaign_data.get("start_date")
            end_date = campaign_data.get("end_date")
            params = campaign_data.get("params", {})

            if not campaign_name or not start_date or not end_date:
                logger.error("Некоторые обязательные поля отсутствуют.")
                await message.reply("Некоторые обязательные данные отсутствуют. Пожалуйста, начните процесс заново.")
                await state.set_state(AddCampaignState.waiting_for_campaign_name)
                return

            db = SessionLocal()
            chat_id = str(message.chat.id)

            # Получаем компанию
            company = get_company_by_chat_id(db, chat_id)
            if not company:
                logger.error(f"Компания не найдена для chat_id: {chat_id}")
                await message.reply("Ошибка: Компания не найдена.")
                return

            # Создаем тему
            bot = message.bot
            thread_name = f"Кампания: {campaign_name}"
            created_thread_id = await create_thread(bot, chat_id, thread_name)

            if not created_thread_id:
                logger.warning(f"Тема для кампании '{campaign_name}' не была добавлена в чат.")
                await message.reply(f"Кампания '{campaign_name}' успешно создана, но тема не была добавлена в чат.")
                await state.set_state(BaseState.default)
                return

            # Сохраняем тему и кампанию
            save_thread_to_db(db, chat_id, created_thread_id, thread_name)
            campaign_data["thread_id"] = created_thread_id
            new_campaign = save_campaign_to_db(db, company.company_id, campaign_data)

            logger.info(f"Кампания создана: id={new_campaign.campaign_id}, name={new_campaign.campaign_name}")
            await message.reply(
                f"Кампания '{new_campaign.campaign_name}' успешно создана, и тема '{thread_name}' добавлена в чат!"
            )
            await state.clear()
            #
            # # Сохраняем идентификатор кампании для создания контентного плана
            # await state.update_data(campaign_id=new_campaign.campaign_id)
            #
            # # Переходим к следующему опросу
            # await handle_add_content_plan(message, state)

        except Exception as e:
            logger.error(f"Непредвиденная ошибка в confirm_campaign_creation: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании кампании.")
        finally:
            if db:
                db.close()

    elif message.text.lower() in ["нет", "отмена"]:
        logger.info("Пользователь отменил создание кампании.")
        await message.reply("Добавление кампании отменено.")
        await state.clear()
    else:
        logger.warning(f"Неверное подтверждение: {message.text}")
        await message.reply("Введите 'да' для подтверждения или 'нет' для отмены.")