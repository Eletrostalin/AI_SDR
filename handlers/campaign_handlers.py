from aiogram.filters import StateFilter
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from admin.ThreadManager import create_thread
from logger import logger
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from db.models import Campaigns, ChatThread
from utils.states import AddCampaignState, BaseState
from classifier import extract_campaign_data_with_validation
from aiogram import Router
from aiogram.types import Message, FSInputFile
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
    campaign_name = message.text.strip()

    # Если название кампании непустое
    if campaign_name:
        # Проверяем, если это полный текст с данными кампании
        extracted_info = await process_message(message, message.bot)

        if extracted_info["type"] == "text":  # Проверяем, что это текстовая информация
            # Передаем текст в модель для извлечения данных
            campaign_data = await extract_campaign_data_with_validation(extracted_info['content'], state, message)
            if campaign_data:
                await handle_full_campaign_data(campaign_data, state, message)
                return

        # Если это только название кампании
        await state.update_data(campaign_name=campaign_name)
        await message.reply("Введите дату начала кампании (в формате ГГГГ-ММ-ДД):")
        await state.set_state(AddCampaignState.waiting_for_start_date)
    else:
        await message.reply("Название кампании не может быть пустым. Укажите название ещё раз.")


# Обработка данных кампании, если переданы сразу
async def handle_full_campaign_data(campaign_data: dict, state: FSMContext, message: Message):
    """
    Обрабатывает полный JSON с данными кампании.
    """
    required_fields = ["campaign_name", "start_date", "end_date"]
    missing_fields = [field for field in required_fields if not campaign_data.get(field)]

    # Если все необходимые данные получены
    if not missing_fields:
        # Сохраняем данные и подтверждаем
        await state.update_data(campaign_data=campaign_data)
        await confirm_campaign_creation(message, state)
    else:
        # Если данные неполные, направляем в соответствующие состояния
        await state.update_data(campaign_data=campaign_data)

        if "campaign_name" in missing_fields:
            await message.reply("Название кампании отсутствует. Укажите его:")
            await state.set_state(AddCampaignState.waiting_for_campaign_name)
        elif "start_date" in missing_fields:
            await message.reply("Дата начала кампании отсутствует. Укажите ее в формате ГГГГ-ММ-ДД:")
            await state.set_state(AddCampaignState.waiting_for_start_date)
        elif "end_date" in missing_fields:
            await message.reply("Дата окончания кампании отсутствует. Укажите ее в формате ГГГГ-ММ-ДД:")
            await state.set_state(AddCampaignState.waiting_for_end_date)


# Обработка даты начала кампании
@router.message(StateFilter(AddCampaignState.waiting_for_start_date))
async def process_start_date(message: Message, state: FSMContext):
    """
    Обрабатывает сообщение с датой начала кампании.
    """
    start_date = message.text.strip()
    try:
        from datetime import datetime
        # Проверяем формат ДД.ММ.ГГГГ
        datetime.strptime(start_date, "%d.%m.%Y")
        await state.update_data(start_date=start_date)
        await message.reply("Введите дату окончания кампании (в формате ДД.ММ.ГГГГ):")
        await state.set_state(AddCampaignState.waiting_for_end_date)
    except ValueError:
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
        await state.update_data(end_date=end_date)
        await message.reply(
            "Укажите дополнительные параметры"
        )
        await state.set_state(AddCampaignState.waiting_for_params)
    except ValueError:
        await message.reply("Некорректный формат даты. Укажите дату окончания в формате ДД.ММ.ГГГГ.")



@router.message(StateFilter(AddCampaignState.waiting_for_params))
async def process_campaign_params(message: Message, state: FSMContext):
    """
    Обрабатывает параметры кампании. Пользователь вводит ключ: значение.
    """
    text = message.text.strip()
    if text.lower() == "готово":
        # Завершаем ввод параметров и показываем подтверждение
        state_data = await state.get_data()
        campaign_name = state_data.get("campaign_name", "Не указано")
        start_date = state_data.get("start_date", "Не указано")
        end_date = state_data.get("end_date", "Не указано")
        params = state_data.get("params", {})
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
        async with state.proxy() as data:
            if "params" not in data:
                data["params"] = {}
            data["params"][key] = value

        # Сразу запрашиваем следующую строку
        await message.reply("Параметр добавлен. Укажите следующий параметр или напишите 'готово', чтобы продолжить.")


@router.message(StateFilter(AddCampaignState.waiting_for_confirmation))
async def confirm_campaign_creation(message: Message, state: FSMContext):
    """
    Подтверждает добавление кампании в базу данных и создает тему в чате.
    """
    if message.text.lower() in ["да", "верно"]:
        # Получаем данные из состояния
        state_data = await state.get_data()
        campaign_name = state_data.get("campaign_name", "Не указано")
        start_date = state_data.get("start_date", "Не указано")
        end_date = state_data.get("end_date", "Не указано")
        params = state_data.get("params", {})

        db = SessionLocal()
        try:
            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)
            if not company:
                await message.reply("Ошибка: Компания не найдена.")
                return

            # Создаем новую кампанию
            new_campaign = Campaigns(
                company_id=company.company_id,
                campaign_name=campaign_name,
                start_date=start_date,
                end_date=end_date,
                params=params,
            )
            db.add(new_campaign)
            db.commit()

            # Создаем тему в чате
            bot = message.bot
            thread_name = f"Кампания: {campaign_name}"
            created_thread_id = await create_thread(bot, chat_id, thread_name)
            if created_thread_id:
                new_thread = ChatThread(
                    chat_id=chat_id,
                    thread_id=created_thread_id,
                    thread_name=thread_name,
                )
                db.add(new_thread)
                db.commit()
                await message.reply(
                    f"Кампания '{campaign_name}' успешно создана, и тема '{thread_name}' добавлена в чат!"
                )
            else:
                await message.reply(f"Кампания '{campaign_name}' успешно создана, но тема не была добавлена в чат.")

            await state.set_state(BaseState.default)
        except SQLAlchemyError as e:
            await message.reply(f"Ошибка при добавлении кампании: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"Ошибка при создании кампании: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании кампании.")
        finally:
            db.close()
    else:
        await message.reply("Добавление кампании отменено.")
        await state.set_state(BaseState.default)