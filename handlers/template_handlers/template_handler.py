from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from agents.tempate_agent import async_template_generation_tool, async_invite_tool
from db.db import SessionLocal
from db.models import Templates, Waves, Company, CompanyInfo, ContentPlan, Campaigns, ChatThread
from states.states import TemplateStates
import logging

logger = logging.getLogger(__name__)
router = Router()


# Обработчик команды /add_template
@router.message(Command("add_template"))
async def add_template(message: types.Message, state: FSMContext):
    """
    Запускает процесс создания шаблона. Предлагает пользователю выбрать контент-план.
    """
    db = SessionLocal()
    chat_id = str(message.chat.id)
    thread_id = message.message_thread_id  # Получаем thread_id из сообщения

    try:
        logger.info(f"📨 [User {message.from_user.id}] Запуск add_template, thread_id={thread_id}")

        # Получаем кампанию по thread_id
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            await message.reply("Кампания, связанная с этим чатом, не найдена.")
            logger.warning(f"❌ Кампания не найдена для thread_id={thread_id}")
            return

        logger.debug(f"✅ Найдена кампания: {campaign.campaign_id} ({campaign.campaign_name})")

        # Получаем компанию, связанную с кампанией
        company = db.query(Company).filter_by(company_id=campaign.company_id).first()
        if not company:
            await message.reply("Компания для данной кампании не найдена.")
            logger.warning(f"❌ Компания не найдена для campaign_id={campaign.campaign_id}")
            return

        logger.debug(f"✅ Найдена компания: {company.company_id} ({company.name})")

        # Получаем информацию о компании (где хранится industry)
        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()
        industry = company_info.industry if company_info else None

        if not industry:
            await message.reply("Отрасль компании не найдена. Проверьте заполненные данные.")
            logger.warning(f"⚠️ Отрасль компании не найдена для company_id={company.company_id}")
            return

        logger.debug(f"✅ Определена отрасль компании: {industry}")

        # Получаем список контент-планов для данной кампании
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign.campaign_id).all()

        if not content_plans:
            await message.reply("Для этой кампании нет доступных контентных планов.")
            logger.warning(f"⚠️ Нет контент-планов для campaign_id={campaign.campaign_id}")
            return

        logger.debug(f"📌 Найдено {len(content_plans)} контент-планов для campaign_id={campaign.campaign_id}")

        # Создаем инлайн-кнопки для выбора контентного плана
        keyboard = InlineKeyboardBuilder()
        for content_plan in content_plans:
            keyboard.add(InlineKeyboardButton(
                text=content_plan.description or f"Контент-план {content_plan.content_plan_id}",
                callback_data=f"select_content_plan:{content_plan.content_plan_id}"
            ))

        # Отправляем пользователю выбор
        await message.reply("Выберите контентный план:", reply_markup=keyboard.as_markup())

        # ✅ Сохраняем `company_id` в FSMContext (его не было!)
        await state.update_data(
            company_id=company.company_id,
            company_name=company.name,
            campaign_id=campaign.campaign_id,
            industry=industry
        )

        logger.info(f"✅ Данные сохранены в FSMContext: company_id={company.company_id}, industry={industry}")

    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при инициализации. Попробуйте позже.")
    finally:
        db.close()


@router.callback_query(lambda c: c.data.startswith("select_content_plan:"))
async def process_content_plan_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор контентного плана пользователем и предлагает выбрать волну.
    """
    content_plan_id = int(callback.data.split(":")[1])
    db = SessionLocal()

    try:
        # Получаем контентный план
        content_plan = db.query(ContentPlan).filter_by(content_plan_id=content_plan_id).first()
        if not content_plan:
            await callback.message.reply("Выбранный контентный план не найден.")
            return

        # Получаем список волн, связанных с этим контентным планом
        waves = db.query(Waves).filter_by(content_plan_id=content_plan_id).all()

        if not waves:
            await callback.message.reply("В этом контентном плане нет доступных волн.")
            return

        # Создаем инлайн-кнопки для выбора волны
        keyboard = InlineKeyboardBuilder()
        for wave in waves:
            keyboard.add(InlineKeyboardButton(
                text=f"{wave.subject} ({wave.send_date.strftime('%Y-%m-%d')})",
                callback_data=f"select_wave:{wave.wave_id}"
            ))

        # Отправляем пользователю выбор волн
        await callback.message.reply("Выберите волну рассылки:", reply_markup=keyboard.as_markup())

        # Сохраняем выбранный контент-план в FSM
        await state.update_data(content_plan_id=content_plan_id, content_plan_desc=content_plan.description)

    except Exception as e:
        logger.error(f"Ошибка при выборе контентного плана: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


@router.callback_query(lambda c: c.data.startswith("select_wave:"))
async def process_wave_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор волны пользователем и запрашивает пожелания к шаблону с AI-генерацией.
    """
    wave_id = int(callback.data.split(":")[1])

    logger.debug(f"⚡ Выбрана волна ID: {wave_id}")  # Логируем факт выбора волны

    db = SessionLocal()
    try:
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            await callback.message.reply("Выбранная волна не найдена.")
            return

        await state.update_data(wave_id=wave_id, subject=wave.subject)  # Сохраняем wave_id в FSMContext

        # 🔹 **Используем AI для генерации приглашения**
        try:
            invite_message = await async_invite_tool()
            if not invite_message:
                raise ValueError("AI вернул пустое приглашение.")

            await callback.message.reply(invite_message)

        except Exception as e:
            logger.error(f"Ошибка при генерации приглашения: {e}", exc_info=True)
            await callback.message.reply("Введите пожелания для генерации шаблона.")  # fallback сообщение

        await state.set_state(TemplateStates.waiting_for_description)

    except Exception as e:
        logger.error(f"Ошибка при выборе волны: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


@router.message(StateFilter(TemplateStates.waiting_for_description))
async def handle_user_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод пользователя и вызывает AI-агента для генерации шаблона (без лишних параметров).
    """
    user_input = message.text.strip()
    state_data = await state.get_data()

    # Подставляем тему письма из выбранной волны
    subject = state_data.get("subject")

    logger.debug(f"Пользовательский ввод: {user_input}")
    logger.debug(f"Тема письма (из волны): {subject}")

    # Проверяем, что все нужные данные есть в состоянии
    required_fields = ["company_name", "industry", "content_plan_desc", "subject"]
    missing_fields = [field for field in required_fields if field not in state_data]

    if missing_fields:
        logger.error(f"Отсутствуют данные в состоянии: {missing_fields}")
        await message.reply("Произошла ошибка. Внутренние данные отсутствуют. Попробуйте снова.")
        return

    # Обновляем состояние пользователя с пожеланиями
    await state.update_data(user_request=user_input)

    # Генерация текста письма через LangChain (без audience, goal, tone, region)
    try:
        template_response = await async_template_generation_tool({
            "company_name": state_data["company_name"],
            "industry": state_data["industry"],
            "content_plan": state_data["content_plan_desc"],
            "subject": subject,
            "user_request": user_input,
        })

        logger.debug(f"Сгенерированный шаблон: {template_response}")

        # Сохраняем результат в состояние
        await state.update_data(template_content=template_response)

        # Отправляем пользователю с запросом подтверждения
        await message.reply(f"Сгенерированный шаблон:\n\n{template_response}\n\nПодтвердите? (да/нет)")
        await state.set_state(TemplateStates.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка при генерации шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при генерации шаблона. Попробуйте позже.")


@router.message(TemplateStates.waiting_for_confirmation)
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон и сохраняет его, связав с выбранной волной.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id  # Получаем chat_id из сообщения
    state_data = await state.get_data()
    db = SessionLocal()

    logger.info(f"✅ [User {user_id}] Начал подтверждение шаблона...")

    try:
        if message.text.strip().lower() != "да":
            await message.reply("Попробуйте снова.")
            logger.info(f"❌ [User {user_id}] Отклонил шаблон.")
            return

        # Проверяем, что в FSMContext есть нужные данные
        required_fields = ["company_id", "subject", "template_content", "user_request", "wave_id"]
        missing_fields = [field for field in required_fields if field not in state_data]

        if missing_fields:
            logger.error(f"❌ [User {user_id}] Ошибка: отсутствуют данные в FSMContext: {missing_fields}")
            await message.reply("Произошла ошибка. Отсутствуют внутренние данные. Попробуйте снова.")
            return

        company_id = state_data["company_id"]
        wave_id = state_data["wave_id"]

        logger.info(f"🔍 [User {user_id}] company_id: {company_id}, wave_id: {wave_id}")

        # 🔍 Получаем thread_id из ChatThread по chat_id
        chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id).first()
        if not chat_thread:
            logger.error(f"❌ [User {user_id}] ChatThread не найден для chat_id: {chat_id}")
            await message.reply("Ошибка: не удалось найти кампанию, связанную с этим чатом.")
            return

        thread_id = chat_thread.thread_id
        logger.info(f"📌 [User {user_id}] Найден thread_id: {thread_id}")

        # 🔍 Получаем кампанию по thread_id
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            logger.error(f"❌ [User {user_id}] Кампания не найдена для thread_id: {thread_id}")
            await message.reply("Ошибка: не удалось найти кампанию, связанную с этим чатом.")
            return

        campaign_id = campaign.campaign_id
        logger.info(f"📢 [User {user_id}] Найдена кампания: {campaign_id}")

        # ✅ Создаём новый шаблон с привязкой к волне
        new_template = Templates(
            company_id=company_id,
            campaign_id=campaign_id,
            wave_id=wave_id,  # Привязываем к выбранной волне
            subject=state_data["subject"],
            template_content=state_data["template_content"],
            user_request=state_data["user_request"],
        )

        db.add(new_template)
        db.commit()
        logger.info(f"✅ [User {user_id}] Шаблон сохранён! Тема: {state_data['subject']}, Волна: {wave_id}")

        await message.reply("Шаблон успешно сохранён и привязан к волне!")
        await state.clear()

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при сохранении шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при сохранении шаблона. Попробуйте позже.")

    finally:
        db.close()
