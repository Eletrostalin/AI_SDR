import json
from aiogram.filters import StateFilter
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.sql import text
from datetime import datetime
from db.db import SessionLocal
from db.db_content_plan import create_content_plan, add_wave
from states.states import AddContentPlanState
from logger import logger
from utils.utils import send_to_model  # Функция для отправки текста в модель

router = Router()


@router.message(StateFilter(None))
async def handle_add_content_plan(message: Message, state: FSMContext):
    """
    Запрашивает у пользователя запрещенные темы и слова для контент-плана.
    """
    await message.answer("Давайте создадим контент-план. Укажите запрещенные темы и слова.")
    await state.set_state(AddContentPlanState.waiting_for_restricted_topics)


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
                         "1️⃣ Холодные лиды\n"
                         "2️⃣ Тёплые лиды\n"
                         "3️⃣ Клиенты\n"
                         "4️⃣ Смешанная\n\n"
                         "**Стиль общения:**\n"
                         "1️⃣ Официально-деловой\n"
                         "2️⃣ Дружелюбно-профессиональный\n"
                         "3️⃣ Эмоционально-убедительный\n"
                         "4️⃣ Экспертно-консультативный\n"
                         "5️⃣ Минималистичный\n\n"
                         "Введите цифры (например, '2 4') или текст.")

    await state.set_state(AddContentPlanState.waiting_for_audience_style)


@router.message(StateFilter(AddContentPlanState.waiting_for_audience_style))
async def process_audience_style(message: Message, state: FSMContext):
    """
    Обрабатывает ввод аудитории и стиля общения, отправляет в модель для анализа.
    """
    user_input = message.text.strip()
    logger.debug(f"📩 Входные данные пользователя: {user_input}")

    # Промпт для модели
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

    logger.debug(f"📡 Отправляем запрос в модель с prompt: {prompt}")

    response = send_to_model(prompt)

    try:
        # Логирование ответа перед обработкой
        logger.debug(f"📬 Ответ модели: {response}")

        model_data = json.loads(response)
        audience = model_data.get("audience", "").strip()
        style = model_data.get("style", "").strip()

        if not audience or not style:
            logger.warning("⚠️ Модель вернула пустые значения. Повторный ввод.")
            await message.reply("⚠️ Не удалось определить аудиторию и стиль. Попробуйте ещё раз.")
            return

        logger.info(f"✅ Определено моделью: Аудитория - {audience}, Стиль - {style}")

        await state.update_data(audience=audience, style=style)
        await state.update_data(wave_count=1)  # Всегда 1 волна

        await message.answer("📅 Укажите дату отправки контент-плана (в формате ДД.ММ.ГГГГ):")
        await state.set_state(AddContentPlanState.waiting_for_send_date)

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка обработки данных от модели: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при анализе ответа. Попробуйте ещё раз.")


@router.message(StateFilter(AddContentPlanState.waiting_for_send_date))
async def process_send_date(message: Message, state: FSMContext):
    """
    Обрабатывает ввод даты отправки контент-плана и сохраняет его в БД.
    """
    user_input = message.text.strip()

    try:
        send_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        await state.update_data(send_date=send_date.isoformat())  # Сохраняем дату в ISO-формате
    except ValueError:
        await message.reply("⚠️ Некорректный формат даты. Введите в формате ДД.ММ.ГГГГ.")
        return

    # Получаем данные из состояния
    state_data = await state.get_data()
    campaign_data = state_data.get("campaign_data", {})
    company_id = campaign_data.get("company_id")  # Исправлено
    campaign_id = campaign_data.get("campaign_id")  # Кампания теперь точно извлекается
    telegram_id = message.from_user.id
    restricted_topics = state_data.get("restricted_topics", "")
    audience = state_data.get("audience", "")
    style = state_data.get("style", "")
    wave_count = state_data.get("wave_count", 1)
    send_date = state_data.get("send_date")

    if not company_id or not campaign_id:
        logger.error(f"❌ Ошибка: company_id или campaign_id отсутствует. Данные: {state_data}")
        await message.reply("❌ Ошибка: Кампания не найдена.")
        return

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
                company_id=company_id,  # Теперь передается корректно
                chat_id=telegram_id,
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
                subject="Первая волна"
            )

            if not wave:
                raise Exception("Не удалось создать волну.")

        await message.answer("✅ Контент-план успешно создан.")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при сохранении контент-плана: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при сохранении контент-плана. Попробуйте позже.")