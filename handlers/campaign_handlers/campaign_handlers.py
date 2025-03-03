from aiogram.types import FSInputFile
from sqlalchemy.sql import text
from aiogram.filters import StateFilter
from admin.ThreadManager import create_thread
from db.db_campaign import create_campaign_and_thread, save_campaign_to_db
from db.db_thread import save_thread_to_db
from handlers.content_plan_handlers.content_plan_handlers import handle_add_content_plan
from logger import logger
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from promts.campaign_promt import EMAIL_SEGMENT_COLUMNS
from states.states import AddCampaignState
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.segment_utils import extract_filters_from_text, apply_filters_to_email_table, generate_excel_from_df

router = Router()



@router.message(StateFilter(None))
async def handle_add_campaign(message: Message, state: FSMContext):
    """
    Инициирует создание рекламной кампании.
    Запрашивает у пользователя название.
    """
    await message.answer("Отлично! 🚀 Давайте настроим кампанию. Я помогу Вам на каждом этапе.")
    await message.answer("Пожалуйста, укажите название рекламной кампании 🏷️")

    # Устанавливаем состояние ожидания ввода названия кампании
    await state.set_state(AddCampaignState.waiting_for_campaign_name)


@router.message(StateFilter(AddCampaignState.waiting_for_campaign_name))
async def process_campaign_name(message: Message, state: FSMContext):
    """
    Обрабатывает введенное название кампании, создаёт запись в БД и тему чата.
    """
    campaign_name = message.text.strip()

    if not campaign_name:
        await message.answer("⚠️ Название кампании не может быть пустым. Попробуйте ещё раз.")
        return

    chat_id = message.chat.id
    bot = message.bot

    try:
        with SessionLocal() as db:
            # ✅ Создаём кампанию
            new_campaign = await create_campaign_and_thread(bot, db, chat_id, campaign_name)

            # ✅ Получаем email_table_id для компании
            email_table = db.execute(
                text("SELECT email_table_id FROM email_tables WHERE company_id = :company_id"),
                {"company_id": new_campaign.company_id}
            ).fetchone()

            if not email_table:
                logger.warning(f"⚠️ Не найдена email-таблица для company_id={new_campaign.company_id}")
                email_table_id = None
            else:
                email_table_id = email_table[0]
                logger.info(f"📩 Используем email_table_id={email_table_id} для компании {new_campaign.company_id}")

        # ✅ Сохраняем данные в state
        campaign_data = {
            "campaign_id": new_campaign.campaign_id,
            "campaign_name": campaign_name,
            "company_id": new_campaign.company_id,
            "email_table_id": email_table_id
        }
        await state.update_data(campaign_data=campaign_data)
        logger.debug(f"✅ Кампания сохранена в state: {campaign_data}")

        # ✅ Отправляем сообщение о фильтрации в созданную тему
        EMAIL_SEGMENT_TRANSLATIONS = {
            "name": "Название компании",
            "region": "Регион",
            "msp_registry": "Реестр МСП",
            "director_name": "Имя директора",
            "director_position": "Должность директора",
            "phone_number": "Телефон",
            "email": "Email",
            "website": "Веб-сайт",
            "primary_activity": "Основная деятельность",
            "revenue": "Выручка",
            "employee_count": "Количество сотрудников"
        }

        segment_columns = ", ".join(
            EMAIL_SEGMENT_TRANSLATIONS.get(col, col) for col in EMAIL_SEGMENT_COLUMNS
        )

        await message.bot.send_message(
            chat_id=chat_id,
            message_thread_id=new_campaign.thread_id,
            text=f"(Доступны только те поля, в которых заполнено хотя бы одно значение)\n\n"
                 f"🔹 {segment_columns}\n\n"
                 f"Введите ответ в формате:\n"
                 f"\nКритерий - Значение\n\n"
                 f"Вы можете выбрать одно или несколько полей.\n"
                 f"Пример:\n"
                 f"\nРегион - Москва\nИмя директора - Сергей\n"
        )

        # ✅ Устанавливаем состояние ожидания фильтрации
        await state.set_state(AddCampaignState.waiting_for_filters)

    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(StateFilter(AddCampaignState.waiting_for_filters))
async def process_filters(message: Message, state: FSMContext):
    """
    Обрабатывает ввод фильтров сегментации с помощью модели и генерирует Excel-таблицу.
    """
    user_input = message.text.strip()

    try:
        # ✅ Отправляем текст в модель для извлечения фильтров
        filters = extract_filters_from_text(user_input)

        if not filters:
            await message.reply("⚠️ Не удалось определить фильтры. Попробуйте переформулировать.")
            return

        # ✅ Получаем данные кампании
        state_data = await state.get_data()
        campaign_data = state_data.get("campaign_data", {})
        company_id = campaign_data.get("company_id")
        campaign_id = campaign_data.get("campaign_id")
        email_table_id = campaign_data.get("email_table_id")

        logger.debug(f"🔍 Данные из state перед фильтрацией: {campaign_data}")

        if not company_id or not campaign_id or not email_table_id:
            await message.reply("❌ Ошибка: Кампания или email-таблица не найдена.")
            return

        # ✅ Открываем сессию БД и применяем фильтры
        with SessionLocal() as db:
            filtered_df = apply_filters_to_email_table(db, email_table_id, filters)

        if filtered_df.empty:
            await message.reply("⚠️ По заданным фильтрам не найдено ни одной записи.")
            return

        # ✅ Генерируем Excel-файл с результатами
        excel_path = generate_excel_from_df(filtered_df, company_id, campaign_id)

        # ✅ Отправляем файл пользователю
        await message.reply_document(
            FSInputFile(excel_path),
            caption="📂 Ваш файл с отфильтрованными email-лидами."
        )

        # ✅ Обновляем данные в состоянии
        campaign_data["filters"] = filters
        await state.update_data(campaign_data=campaign_data)

        logger.info(f"✅ Фильтры успешно применены: {filters}")

        # ✅ Спрашиваем о дате начала кампании
        await message.reply("📅 Укажите дату начала кампании (в формате ДД.ММ.ГГГГ):")
        await state.set_state(AddCampaignState.waiting_for_start_date)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки фильтров через модель: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при обработке фильтров. Попробуйте ещё раз.")


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
    user_input = message.text.strip().lower()
    logger.debug(f"Подтверждение кампании: {user_input}")

    if user_input not in ["да", "нет"]:
        await message.reply("Введите 'да' для подтверждения или 'нет' для отмены.")
        return

    if user_input == "да":
        db = SessionLocal()
        try:
            logger.debug("Начало процесса сохранения кампании.")
            state_data = await state.get_data()
            campaign_data = state_data.get("campaign_data")
            logger.debug(f"Данные кампании из состояния: {campaign_data}")

            chat_id = str(message.chat.id)
            company = get_company_by_chat_id(db, chat_id)
            logger.debug(f"Компания найдена: {company}")

            if not company:
                logger.error(f"Компания не найдена для chat_id={chat_id}")
                await message.reply("Компания не найдена. Добавьте её перед созданием кампании.")
                return

            # Создаём тему и сохраняем кампанию
            bot = message.bot
            thread_name = f"Кампания: {campaign_data['campaign_name']}"
            thread_id = await create_thread(bot, chat_id, thread_name)
            logger.debug(f"Созданный thread_id: {thread_id}")

            if thread_id:
                campaign_data["thread_id"] = thread_id
                await state.update_data(campaign_data=campaign_data)
            else:
                logger.error("Ошибка: thread_id не был создан.")
                raise ValueError("Ошибка: thread_id не был создан.")

            logger.debug(f"Сохранение темы в базу. chat_id={chat_id}, thread_id={thread_id}, thread_name={thread_name}")
            save_thread_to_db(db, chat_id, thread_id, thread_name)

            logger.debug(f"Сохранение кампании в базу. company_id={company.company_id}, campaign_data={campaign_data}")
            save_campaign_to_db(db, company.company_id, campaign_data)

            await message.reply(f"Кампания '{campaign_data['campaign_name']}' успешно создана.")
            logger.info(f"Кампания '{campaign_data['campaign_name']}' успешно сохранена в БД.")

            # Переход к созданию контентного плана
            await message.reply("Теперь создадим контентный план для этой кампании...")
            await handle_add_content_plan(message, state, thread_id=thread_id)  # Передаем thread_id

        except Exception as e:
            logger.error(f"Ошибка создания кампании: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании кампании.")
        finally:
            db.close()
            logger.debug("Закрыто соединение с базой данных.")
    else:
        logger.debug("Создание кампании отменено пользователем.")
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


# text=f"📊 По какому критерию из базы email Вы хотите провести рассылку?\n\n"
#                  f"(Доступны только те поля, в которых заполнено хотя бы одно значение)\n\n"
#                  f"🔹 {segment_columns}\n\n"
#                  f"Введите ответ в формате:\n"
#                  f"\nКритерий - Значение\n\n"
#                  f"Вы можете выбрать одно или несколько полей.\n"
#                  f"Пример:\n"
#                  f"\nРегион - Москва\nИмя директора - Сергей\n"