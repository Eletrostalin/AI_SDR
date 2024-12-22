from aiogram.filters import StateFilter
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# Подтверждение и сохранение
from datetime import datetime
from db.db import SessionLocal
from db.models import ContentPlan, Waves, Campaigns, ChatThread
from states.states import AddContentPlanState
from logger import logger

router = Router()

# Начало создания контентного плана
@router.message(StateFilter(None))
async def handle_add_content_plan(message: Message, state: FSMContext):
    """
    Инициирует процесс добавления контентного плана.
    """
    await message.reply("Введите описание контентного плана.")
    await state.set_state(AddContentPlanState.waiting_for_description)


# Обработка описания контентного плана
@router.message(StateFilter(AddContentPlanState.waiting_for_description))
async def process_content_plan_description(message: Message, state: FSMContext):
    """
    Обрабатывает описание контентного плана.
    """
    description = message.text.strip()
    if not description:
        await message.reply("Описание не может быть пустым. Пожалуйста, введите описание.")
        return

    # Сохраняем описание
    await state.update_data(description=description)
    await message.reply("Введите количество волн в контентном плане.")
    await state.set_state(AddContentPlanState.waiting_for_wave_count)


# Обработка количества волн
@router.message(StateFilter(AddContentPlanState.waiting_for_wave_count))
async def process_wave_count(message: Message, state: FSMContext):
    """
    Обрабатывает количество волн в контентном плане.
    """
    try:
        wave_count = int(message.text.strip())
        if wave_count <= 0:
            raise ValueError

        # Сохраняем количество волн
        await state.update_data(wave_count=wave_count)
        await message.reply(f"Введите данные для каждой из {wave_count} волн.\nФормат: 'дата время тема'. Например: '25.12.2024 15:30 Новогодняя рассылка'.")
        await state.set_state(AddContentPlanState.waiting_for_wave_details)

    except ValueError:
        await message.reply("Некорректное количество волн. Введите положительное целое число.")


# Обработка данных волн
@router.message(StateFilter(AddContentPlanState.waiting_for_wave_details))
async def process_wave_details(message: Message, state: FSMContext):
    """
    Обрабатывает данные о каждой волне контентного плана.
    """
    state_data = await state.get_data()
    wave_count = state_data.get("wave_count", 0)
    waves = state_data.get("waves", [])

    wave_data = message.text.strip().split(maxsplit=2)
    if len(wave_data) != 3:
        await message.reply("Некорректный формат. Введите данные в формате: 'дата время тема'. Например: '25.12.2024 15:30 Новогодняя рассылка'.")
        return

    try:
        from datetime import datetime
        send_date = datetime.strptime(wave_data[0], "%d.%m.%Y")
        send_time = datetime.strptime(wave_data[1], "%H:%M").time()
        subject = wave_data[2]

        waves.append({
            "send_date": send_date.date().isoformat(),
            "send_time": send_time.isoformat(),
            "subject": subject
        })

        await state.update_data(waves=waves)

        if len(waves) == wave_count:
            await message.reply("Все данные волн введены. Подтвердите создание контентного плана. Напишите 'да' для подтверждения или 'нет' для отмены.")
            await state.set_state(AddContentPlanState.waiting_for_confirmation)
        else:
            await message.reply(f"Волна {len(waves)} добавлена. Введите данные для следующей волны (осталось {wave_count - len(waves)}).")

    except ValueError:
        await message.reply("Некорректная дата или время. Убедитесь, что вы используете формат 'дата время тема'.")


# Подтверждение и сохранение
@router.message(StateFilter(AddContentPlanState.waiting_for_confirmation))
async def confirm_content_plan(message: Message, state: FSMContext):
    """
    Подтверждает создание контентного плана и сохраняет его в базу данных.
    """
    if message.text.lower() in ["да", "верно"]:
        state_data = await state.get_data()
        description = state_data.get("description")
        wave_count = state_data.get("wave_count")
        waves = state_data.get("waves", [])

        db = SessionLocal()
        try:
            chat_id = message.chat.id
            thread_id = message.message_thread_id

            # Проверяем наличие thread_id
            if not thread_id:
                await message.reply("Ошибка: не удалось определить связанный thread_id. Попробуйте снова.")
                return

            # Получаем запись о теме из ChatThread
            chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id, thread_id=thread_id).first()
            if not chat_thread:
                logger.error(
                    f"Ошибка: тема с chat_id={chat_id} и thread_id={thread_id} не найдена в таблице ChatThread.")
                await message.reply("Ошибка: тема, связанная с этим thread_id, не найдена.")
                return

            logger.debug(
                f"Тема найдена: thread_name={chat_thread.thread_name}, thread_id={thread_id}, chat_id={chat_id}")

            # Логика для нахождения кампании по thread_id
            campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()

            if not campaign:
                logger.error(
                    f"Ошибка: кампания, связанная с thread_id={thread_id} (chat_id={chat_id}), не найдена."
                )
                await message.reply("Ошибка: кампания, связанная с этой темой, не найдена.")
                return

            logger.debug(f"Кампания найдена: campaign_id={campaign.campaign_id}, name={campaign.campaign_name}")

            # Создание контентного плана
            content_plan = ContentPlan(
                company_id=campaign.company_id,
                telegram_id=str(chat_id),
                description=description,
                wave_count=wave_count,
                campaign_id=campaign.campaign_id
            )
            db.add(content_plan)
            db.commit()
            db.refresh(content_plan)

            # Добавление волн
            for wave in waves:
                try:
                    # Определяем формат времени в зависимости от наличия секунд
                    send_time_str = wave["send_time"]
                    if len(send_time_str) == 5:  # Формат HH:MM
                        time_obj = datetime.strptime(send_time_str, "%H:%M").time()
                    elif len(send_time_str) == 8:  # Формат HH:MM:SS
                        time_obj = datetime.strptime(send_time_str, "%H:%M:%S").time()
                    else:
                        raise ValueError(f"Некорректный формат времени: {send_time_str}")

                    # Объединяем дату и время
                    combined_datetime = datetime.combine(
                        datetime.strptime(wave["send_date"], "%Y-%m-%d"),  # Дата в формате YYYY-MM-DD
                        time_obj
                    )

                    db.add(Waves(
                        content_plan_id=content_plan.content_plan_id,
                        company_id=campaign.company_id,
                        campaign_id=campaign.campaign_id,
                        send_date=combined_datetime.date(),  # Только дата
                        send_time=combined_datetime,  # Полный datetime
                        subject=wave["subject"]
                    ))
                except ValueError as e:
                    logger.error(f"Ошибка обработки волны: {wave}. Детали: {e}")
                    await message.reply(f"Ошибка в данных волны: {wave['subject']}. Проверьте дату и время.")
                    db.rollback()
                    return

            db.commit()

            # Уведомление пользователя
            await message.reply(
                f"Контентный план '{description}' успешно создан для кампании '{campaign.campaign_name}'!"
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Ошибка при создании контентного плана: {e}", exc_info=True)
            await message.reply("Произошла ошибка при создании контентного плана. Попробуйте снова.")
            db.rollback()
        finally:
            db.close()

    elif message.text.lower() in ["нет", "отмена"]:
        await message.reply("Создание контентного плана отменено.")
        await state.clear()
    else:
        await message.reply("Введите 'да' для подтверждения или 'нет' для отмены.")