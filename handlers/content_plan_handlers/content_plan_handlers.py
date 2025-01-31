from aiogram.filters import StateFilter
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# Подтверждение и сохранение
from datetime import datetime
from db.db import SessionLocal
from db.db_content_plan import get_chat_thread, get_campaign_by_thread_id, create_content_plan, add_wave
from db.models import ContentPlan, Waves, Campaigns, ChatThread
from states.states import AddContentPlanState
from logger import logger

router = Router()

# Начало создания контентного плана
@router.message(StateFilter(None))
async def handle_add_content_plan(message: Message, state: FSMContext, thread_id: int = None):
    """
    Инициирует процесс добавления контентного плана.
    """
    if thread_id:
        # Сохраняем переданный thread_id в состояние
        await state.update_data(thread_id=thread_id)
        logger.debug(f"Переданный thread_id: {thread_id}")
    else:
        # Используем thread_id из сообщения, если он не был передан
        thread_id = message.message_thread_id
        if not thread_id:
            await message.reply("Ошибка: не удалось определить связанный thread_id. Попробуйте снова.")
            return

        await state.update_data(thread_id=thread_id)

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
            # Выводим все введённые данные для подтверждения
            waves_info = "\n".join(
                [f"{idx + 1}. Дата: {wave['send_date']}, Время: {wave['send_time']}, Тема: {wave['subject']}" for idx, wave in enumerate(waves)]
            )
            confirmation_message = (
                f"Все данные волн введены. Вот что вы ввели:\n\n"
                f"{waves_info}\n\n"
                "Подтвердите создание контентного плана. Напишите 'да' для подтверждения или 'нет' для отмены."
            )
            await message.reply(confirmation_message)
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
        thread_id = state_data.get("thread_id")  # Получаем thread_id из состояния

        db = SessionLocal()
        try:
            chat_id = message.chat.id

            # Получаем тему
            chat_thread = get_chat_thread(db, chat_id, thread_id)
            if not chat_thread:
                logger.error(f"Ошибка: тема, связанная с thread_id={thread_id}, не найдена.")
                await message.reply("Ошибка: тема, связанная с этим thread_id, не найдена.")
                db.close()
                return

            logger.debug(
                f"Тема найдена: thread_name={chat_thread.thread_name}, thread_id={thread_id}, chat_id={chat_id}"
            )

            # Получаем кампанию
            campaign = get_campaign_by_thread_id(db, thread_id)
            if not campaign:
                logger.error(f"Ошибка: кампания, связанная с thread_id={thread_id}, не найдена.")
                await message.reply("Ошибка: кампания, связанная с этой темой, не найдена.")
                db.close()
                return

            logger.debug(f"Кампания найдена: campaign_id={campaign.campaign_id}, name={campaign.campaign_name}")

            # Логируем перед созданием контентного плана
            logger.debug(
                f"Создаем контентный план с параметрами: company_id={campaign.company_id}, chat_id={chat_id}, "
                f"description={description}, wave_count={wave_count}, campaign_id={campaign.campaign_id}"
            )

            # Создаем контентный план
            content_plan = create_content_plan(
                db=db,
                company_id=campaign.company_id,
                chat_id=chat_id,
                description=description,
                wave_count=wave_count,
                campaign_id=campaign.campaign_id
            )

            # Проверяем, успешно ли создан контентный план
            if not content_plan:
                logger.error("Ошибка: create_content_plan вернул None. Контентный план не был создан.")
                await message.reply("Ошибка при создании контентного плана. Попробуйте снова.")
                db.rollback()
                db.close()
                return

            logger.debug(f"Контентный план успешно создан: content_plan_id={content_plan.content_plan_id}")

            # Добавляем волны
            for wave in waves:
                # Проверка и преобразование send_time
                send_time = wave.get("send_time")
                if isinstance(send_time, str):
                    send_time = datetime.strptime(send_time, "%H:%M:%S").time()
                elif isinstance(send_time, datetime):
                    send_time = send_time.time()
                else:
                    logger.error(f"Ошибка в формате времени волны: {send_time}")
                    raise ValueError(f"Неподдерживаемый формат времени: {send_time}")

                # Преобразование даты и времени в datetime
                send_date = wave["send_date"]
                send_datetime = datetime.strptime(
                    f"{send_date} {send_time}", "%Y-%m-%d %H:%M:%S"
                )

                logger.debug(
                    f"Добавляем волну: send_date={send_date}, send_time={send_time}, subject={wave['subject']}"
                )

                add_wave(
                    db=db,
                    content_plan_id=content_plan.content_plan_id,
                    company_id=campaign.company_id,
                    campaign_id=campaign.campaign_id,
                    wave={
                        "send_time": send_datetime,
                        "send_date": send_date,
                        "subject": wave["subject"]
                    }
                )

            db.commit()
            logger.info(
                f"Контентный план '{description}' успешно создан для кампании '{campaign.campaign_name}'!"
            )
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
