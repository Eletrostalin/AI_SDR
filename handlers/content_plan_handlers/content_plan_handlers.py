import json
from aiogram.filters import StateFilter
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.sql import text
from datetime import datetime
from db.db import SessionLocal
from db.db_content_plan import create_content_plan, add_wave
from db.models import User, Campaigns, Company, ChatThread
from handlers.template_handlers.template_handler import add_template
from states.states import AddContentPlanState
from logger import logger
from utils.utils import send_to_model  # Функция для отправки текста в модель # Импортируем первую функцию модуля шаблонов

router = Router()


@router.message(StateFilter(None))
async def handle_add_content_plan(message: Message, state: FSMContext):
    """
    Запрашивает у пользователя запрещенные темы и слова для контент-плана.
    """
    db = SessionLocal()
    try:
        chat_id = message.chat.id
        thread_id = message.message_thread_id  # thread_id, если есть
        user_id = message.from_user.id

        # 1️⃣ **Ищем компанию через chat_id**
        company = db.query(Company).filter_by(chat_id=str(chat_id)).first()
        if not company:
            logger.error(f"❌ Ошибка: Компания не найдена для чата {chat_id}.")
            await message.answer("❌ Ошибка: Ваша компания не найдена. Обратитесь к администратору.")
            return
        company_id = company.company_id

        # 2️⃣ **Ищем кампанию через thread_id**
        campaign = None
        if thread_id:
            chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
            if chat_thread:
                campaign = db.query(Campaigns).filter_by(thread_id=chat_thread.thread_id).first()

        if not campaign:
            logger.error(f"❌ Ошибка: Кампания не найдена для chat_id={chat_id}, thread_id={thread_id}.")
            await message.answer("❌ Ошибка: Кампания не найдена. Убедитесь, что вы выбрали нужный тред или есть активная кампания.")
            return

        campaign_id = campaign.campaign_id

        # ✅ **Сохраняем в FSM внутри campaign_data**
        await state.update_data(campaign_data={"company_id": company_id, "campaign_id": campaign_id})

        logger.info(f"✅ Загружены данные: company_id={company_id}, campaign_id={campaign_id}")

        await message.answer("Давайте создадим контент-план. Укажите запрещенные темы и слова.")
        await state.set_state(AddContentPlanState.waiting_for_restricted_topics)

    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке данных компании/кампании: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при загрузке данных. Попробуйте позже.")
    finally:
        db.close()


@router.message(StateFilter(AddContentPlanState.waiting_for_restricted_topics))
async def process_restricted_topics(message: Message, state: FSMContext):
    """
    Сохраняет запрещенные темы и слова, переходит к выбору аудитории и стиля общения.
    """
    restricted_topics = message.text.strip()
    await state.update_data(restricted_topics=restricted_topics)

    await message.answer("Опишите аудиторию и стиль общения для контент-плана.\n\n"
                         "Вы можете использовать текст или выбрать из вариантов:\n\n"
                         "**Аудитория:**\n"
                         "1. Холодные лиды\n"
                         "2. Тёплые лиды\n"
                         "3. Клиенты\n"
                         "4. Смешанная\n\n"
                         "**Стиль общения:**\n"
                         "1. Официально-деловой\n"
                         "2. Дружелюбно-профессиональный\n"
                         "3. Эмоционально-убедительный\n"
                         "4. Экспертно-консультативный\n"
                         "5. Минималистичный\n\n"
                         "Введите цифры (например, '2 4') или текст.")

    await state.set_state(AddContentPlanState.waiting_for_audience_style)


@router.message(StateFilter(AddContentPlanState.waiting_for_audience_style))
async def process_audience_style(message: Message, state: FSMContext):
    """
    Обрабатывает ввод аудитории и стиля общения, отправляет в модель для анализа.
    """
    user_input = message.text.strip()
    logger.debug(f"Входные данные пользователя: {user_input}")

    prompt = f"""
    Ты — эксперт по маркетинговым коммуникациям. Определи параметры контент-плана на основе текста пользователя.

    **Доступные аудитории:**
    - Холодные лиды
    - Тёплые лиды
    - Клиенты
    - Смешанная

    **Доступные стили общения:**
    - Официально-деловой стиль
    - Дружелюбно-профессиональный стиль
    - Эмоционально-убедительный стиль
    - Экспертно-консультативный стиль
    - Минималистичный стиль

    **Входной текст пользователя:** "{user_input}"

    **Ответ верни строго в JSON-формате:**
    {{
        "audience": "<аудитория>",
        "style": "<стиль общения>"
    }}
    """

    logger.debug(f"Отправляем запрос в модель с prompt: {prompt}")

    response = send_to_model(prompt)

    try:
        logger.debug(f"Ответ модели: {response}")

        model_data = json.loads(response)
        audience = model_data.get("audience", "").strip()
        style = model_data.get("style", "").strip()

        if not audience or not style:
            logger.warning("Модель вернула пустые значения. Повторный ввод.")
            await message.reply("Не удалось определить аудиторию и стиль. Попробуйте ещё раз.")
            return

        logger.info(f"Определено моделью: Аудитория - {audience}, Стиль - {style}")

        await state.update_data(audience=audience, style=style)
        await state.update_data(wave_count=1)  # Всегда 1 волна

        await message.answer("Введите название волны (например, 'Первая волна'):")
        await state.set_state(AddContentPlanState.waiting_for_wave_name)

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка обработки данных от модели: {e}", exc_info=True)
        await message.reply("Произошла ошибка при анализе ответа. Попробуйте ещё раз.")


@router.message(StateFilter(AddContentPlanState.waiting_for_wave_name))
async def process_wave_name(message: Message, state: FSMContext):
    """
    Сохраняет название волны и запрашивает дату отправки.
    """
    wave_name = message.text.strip()
    await state.update_data(wave_name=wave_name)

    await message.answer("Укажите дату отправки контент-плана (в формате ДД.ММ.ГГГГ):")
    await state.set_state(AddContentPlanState.waiting_for_send_date)


@router.message(StateFilter(AddContentPlanState.waiting_for_send_date))
async def process_send_date(message: Message, state: FSMContext):
    """
    Обрабатывает ввод даты отправки контент-плана и сохраняет его в БД.
    После успешного создания контент-плана запускает процесс генерации шаблона.
    """
    user_input = message.text.strip()

    try:
        send_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        await state.update_data(send_date=send_date.isoformat())  # Сохраняем дату в ISO-формате
    except ValueError:
        await message.reply("⚠️ Некорректный формат даты. Введите в формате ДД.ММ.ГГГГ.")
        return

    # Получаем данные из campaign_data
    state_data = await state.get_data()
    campaign_data = state_data.get("campaign_data", {})

    company_id = campaign_data.get("company_id")
    campaign_id = campaign_data.get("campaign_id")

    if not company_id or not campaign_id:
        logger.error(f"❌ Ошибка: company_id или campaign_id отсутствует. Данные: {state_data}")
        await message.reply("❌ Ошибка: Кампания не найдена.")
        return

    restricted_topics = state_data.get("restricted_topics", "")
    audience = state_data.get("audience", "")
    style = state_data.get("style", "")
    wave_count = state_data.get("wave_count", 1)
    send_date = state_data.get("send_date")
    wave_name = state_data.get("wave_name", "Без названия")

    # Описание контент-плана в JSON-формате
    description = {
        "audience": audience,
        "style": style,
        "restricted_topics": restricted_topics,
        "send_date": send_date
    }

    try:
        with SessionLocal() as db:
            # ✅ Создание контент-плана
            content_plan = create_content_plan(
                db=db,
                company_id=company_id,
                chat_id=message.from_user.id,
                description=description,
                wave_count=wave_count
            )

            if not content_plan:
                raise Exception("Не удалось создать контент-план.")

            # ✅ Добавление волны
            wave = add_wave(
                db=db,
                content_plan_id=content_plan.content_plan_id,
                company_id=company_id,
                campaign_id=campaign_id,
                send_date=send_date,
                subject=wave_name
            )

            if not wave:
                raise Exception("Не удалось создать волну.")

        await message.answer("✅ Контент-план успешно создан.")
        await message.answer("Перейдем к созданию шаблона")

        # **Автоматически вызываем add_template**
        logger.info(f"📌 Запуск генерации шаблона для campaign_id={campaign_id}")
        await add_template(message=message, state=state)

    except Exception as e:
        logger.error(f"Ошибка при сохранении контент-плана: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при сохранении контент-плана. Попробуйте позже.")

    finally:
        await state.clear()  # Очистка состояния после создания контент-плана