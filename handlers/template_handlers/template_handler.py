import asyncio
from datetime import timedelta, datetime

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import db
from db.db_company import get_company_by_chat_id
from db.db_template import get_campaign_by_thread, get_company_by_id, get_content_plans_by_campaign, \
    get_waves_by_content_plan, get_wave_by_id, save_template, get_chat_thread_by_chat_id, \
    get_company_info_and_content_plan, get_content_plan_by_id
from db.models import Templates, Waves, Company, CompanyInfo, ContentPlan, Campaigns, ChatThread
from handlers.draft_handlers.draft_handler import generate_drafts_for_wave
from promts.template_promt import generate_email_template_prompt
from states.states import TemplateStates
import logging

from utils.utils import send_to_model

logger = logging.getLogger(__name__)
router = Router()


# Обработчик команды /add_template
@router.message(Command("add_template"))
async def add_template(message: types.Message, state: FSMContext):
    """
    Запускает процесс создания шаблона. Предлагает пользователю выбрать контент-план.
    """
    # Database operations handled in db_operations module
    chat_id = str(message.chat.id)
    thread_id = message.message_thread_id

    try:
        logger.info(f"[User {message.from_user.id}] Запуск add_template, thread_id={thread_id}")

        # Получаем кампанию по thread_id
        campaign = get_campaign_by_thread(thread_id)
        if not campaign:
            await message.reply("Кампания, связанная с этим чатом, не найдена.")
            logger.warning(f"Кампания не найдена для thread_id={thread_id}")
            return

        logger.debug(f"Найдена кампания: {campaign.campaign_id} ({campaign.campaign_name})")

        # Получаем компанию, связанную с кампанией
        company = get_company_by_id(campaign.company_id)
        if not company:
            await message.reply("Компания для данной кампании не найдена.")
            logger.warning(f"Компания не найдена для campaign_id={campaign.campaign_id}")
            return

        logger.debug(f"Найдена компания: {company.company_id} ({company.name})")

        # Получаем информацию о компании
        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()
        business_sector = company_info.business_sector if company_info else None

        # if not business_sector:
        #     await message.reply("Отрасль компании не найдена. Проверьте заполненные данные.")
        #     logger.warning(f"Отрасль компании (business_sector) не найдена для company_id={company.company_id}")
        #     return
        #
        # logger.debug(f"Определена отрасль компании: {business_sector}")

        # Получаем список контент-планов для кампании
        content_plans = get_content_plans_by_campaign(campaign.campaign_id)
        if not content_plans:
            await message.reply("Для этой кампании нет доступных контентных планов.")
            logger.warning(f"Нет контент-планов для campaign_id={campaign.campaign_id}")
            return

        logger.debug(f"Найдено {len(content_plans)} контент-планов для campaign_id={campaign.campaign_id}")

        # Сохраняем данные в FSMContext
        await state.update_data(
            company_id=company.company_id,
            company_name=company.name or "Неизвестная компания",
            campaign_id=campaign.campaign_id,
            business_sector=business_sector
        )

        logger.info(f"✅ Данные сохранены в FSMContext: company_id={company.company_id}, business_sector={business_sector}")

        # Отправляем выбор контент-планов
        # Генерация кнопок с нумерацией контент-планов
        keyboard = InlineKeyboardBuilder()
        for index, content_plan in enumerate(content_plans, start=1):
            keyboard.add(InlineKeyboardButton(
                text=f"Контент-план {index}",
                callback_data=f"select_content_plan:{content_plan.content_plan_id}"
            ))

        await message.reply("Выберите контентный план:", reply_markup=keyboard.as_markup())

    except Exception as e:
        logger.error(f"Ошибка при инициализации шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при инициализации. Попробуйте позже.")

    # No explicit db session to close


@router.callback_query(lambda c: c.data.startswith("select_content_plan:"))
async def process_content_plan_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор контентного плана пользователем и предлагает выбрать волну.
    """
    content_plan_id = int(callback.data.split(":")[1])
    # Database operations handled in db_operations module

    try:
        # Получаем контентный план
        content_plan = get_content_plan_by_id(content_plan_id)
        if not content_plan:
            await callback.message.reply("Выбранный контентный план не найден.")
            return

        # Получаем список волн, связанных с этим контентным планом
        waves = get_waves_by_content_plan(content_plan_id)
        if not waves:
            await callback.message.reply("В этом контентном плане нет доступных волн.")
            return

        # Сохраняем контент-план в FSM
        await state.update_data(content_plan_id=content_plan.content_plan_id, content_plan_desc=content_plan.description)

        logger.debug(f"✅ Контент-план сохранен в FSMContext: {content_plan.content_plan_id}")

        # Генерация кнопок с нумерацией волн
        keyboard = InlineKeyboardBuilder()
        for index, wave in enumerate(waves, start=1):
            keyboard.add(InlineKeyboardButton(
                text=f"Волна {index} ({wave.send_date.strftime('%Y-%m-%d')})",
                callback_data=f"select_wave:{wave.wave_id}"
            ))
        await callback.message.reply("Выберите волну рассылки:", reply_markup=keyboard.as_markup())

    except Exception as e:
        logger.error(f"Ошибка при выборе контентного плана: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")

    # No explicit db session to close


@router.callback_query(lambda c: c.data.startswith("select_wave:"))
async def process_wave_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор волны пользователем и запрашивает пожелания к шаблону.
    """
    wave_id = int(callback.data.split(":")[1])

    logger.debug(f"Выбрана волна ID: {wave_id}")

    wave = get_wave_by_id(wave_id)
    if not wave:
        await callback.message.reply("Выбранная волна не найдена.")
        return

    # Проверяем, что дата волны не раньше завтрашнего дня
    today = datetime.now().date()
    wave_date = wave.send_date.date()
    if wave_date < today + timedelta(days=1):
        await callback.message.reply(
            "Ошибка: Вы не можете выбрать дату раньше завтрашнего дня.\n"
            "Пожалуйста, выберите новую дату отправки."
        )
        return  # Оставляем пользователя в том же состоянии

    await state.update_data(wave_id=wave_id)

    # Отправляем хардкодное сообщение вместо AI-генерации
    invite_message = (
        "Вы выбрали волну для отправки шаблона.\n"
        "Напишите свои пожелания по содержанию письма, и мы подготовим шаблон."
    )

    await callback.message.reply(invite_message)
    await state.set_state(TemplateStates.waiting_for_description)


async def handle_user_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод пользователя и вызывает AI-ассистента для генерации шаблона.
    """
    user_input = message.text.strip()
    chat_id = str(message.chat.id)

    logger.info(f"[User {message.from_user.id}] Получен ввод для генерации шаблона: {user_input}")

    state_data = await state.get_data()
    logger.debug(f"[User {message.from_user.id}] Данные состояния перед обработкой: {state_data}")

    company_id = state_data.get("company_id")
    content_plan_id = state_data.get("content_plan_id")

    if not company_id:
        logger.warning(f"[User {message.from_user.id}] Company ID отсутствует в FSM, пытаемся найти по chat_id={chat_id}")
        company = get_company_by_chat_id(chat_id)
        if company:
            company_id = company.company_id
            await state.update_data(company_id=company_id)
            logger.info(f"[User {message.from_user.id}] Найден company_id={company_id} и сохранен в FSM.")
        else:
            logger.error(f"[User {message.from_user.id}] Ошибка: компания не найдена.")
            await message.reply("Ошибка: компания не найдена.")
            return

    if not content_plan_id:
        logger.error(f"[User {message.from_user.id}] Ошибка: контент-план не найден в FSM.")
        await message.reply("Ошибка: не удалось найти контент-план.")
        return

    # Получаем информацию о компании и контент-плане
    company_info, content_plan_desc = get_company_info_and_content_plan(company_id, content_plan_id)

    if not company_info:
        logger.error(f"[User {message.from_user.id}] Ошибка: данные компании или контент-план не найдены.")
        await message.reply("Ошибка: не удалось найти данные компании или контент-план.")
        return

    logger.info(f"[User {message.from_user.id}] Данные компании успешно загружены.")

    # Собираем данные для модели
    company_details = {
        "company_name": company_info.company_name or "Неизвестная компания",
        "company_mission": company_info.company_mission,
        "company_values": company_info.company_values,
        "business_sector": company_info.business_sector,
        "office_addresses_and_hours": company_info.office_addresses_and_hours,
        "resource_links": company_info.resource_links,
        "target_audience_b2b_b2c_niche_geography": company_info.target_audience_b2b_b2c_niche_geography,
        "unique_selling_proposition": company_info.unique_selling_proposition,
        "customer_pain_points": company_info.customer_pain_points,
        "competitor_differences": company_info.competitor_differences,
        "promoted_products_and_services": company_info.promoted_products_and_services,
        "delivery_availability_geographical_coverage": company_info.delivery_availability_geographical_coverage,
        "frequently_asked_questions_with_answers": company_info.frequently_asked_questions_with_answers,
        "common_customer_objections_and_responses": company_info.common_customer_objections_and_responses,
        "successful_case_studies": company_info.successful_case_studies,
        "additional_information": company_info.additional_information,
        "content_plan_description": content_plan_desc,
        "user_request": user_input,  # Добавляем запрос пользователя
    }
    company_details = {k: v for k, v in company_details.items() if v}  # Удаляем пустые поля

    logger.debug(f"[User {message.from_user.id}] Подготовленные данные для генерации: {company_details}")

    # Генерируем промпт
    prompt = generate_email_template_prompt(company_details)
    logger.debug(f"[User {message.from_user.id}] Сгенерированный промпт: {prompt}")

    # Отправляем запрос в модель
    template_response = send_to_model(prompt)
    if not template_response:
        logger.error(f"[User {message.from_user.id}] Ошибка при генерации шаблона.")
        await message.reply("Ошибка при генерации шаблона. Попробуйте позже.")
        return

    await state.update_data(template_content=template_response)
    logger.info(f"[User {message.from_user.id}] Шаблон успешно сгенерирован.")

    # Отправляем пользователю сгенерированный шаблон
    await message.reply(f"Сгенерированный шаблон:\n\n{template_response}\n\nПодтвердите? (да/нет)")
    await state.set_state(TemplateStates.waiting_for_confirmation)


@router.message(TemplateStates.waiting_for_confirmation)
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон и сохраняет его в БД.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    state_data = await state.get_data()

    logger.info(f"[User {user_id}] Начал подтверждение шаблона...")

    if message.text.strip().lower() != "да":
        await message.reply("Попробуйте снова. Введите новый запрос для генерации шаблона.")
        logger.info(f"[User {user_id}] Отклонил шаблон. Ожидание нового ввода.")
        await state.set_state(TemplateStates.waiting_for_description)
        return

    required_fields = ["company_id", "template_content", "user_request", "wave_id"]
    missing_fields = [field for field in required_fields if field not in state_data]

    if missing_fields:
        logger.error(f"[User {user_id}] Критическая ошибка: отсутствуют данные {missing_fields}")
        await message.reply("Ошибка: отсутствуют внутренние данные. Попробуйте снова.")
        return

    company_id = state_data["company_id"]
    wave_id = state_data["wave_id"]
    template_content = state_data["template_content"]
    user_request = state_data["user_request"]

    wave = get_wave_by_id(wave_id)
    if not wave:
        logger.error(f"[User {user_id}] Ошибка: не удалось найти волну с wave_id={wave_id}")
        await message.reply("Ошибка: не удалось найти волну. Попробуйте снова.")
        return

    chat_thread = get_chat_thread_by_chat_id(chat_id)
    if not chat_thread:
        await message.reply("Ошибка: не удалось найти кампанию.")
        return

    campaign = get_campaign_by_thread(chat_thread.thread_id)
    if not campaign:
        await message.reply("Ошибка: не удалось найти кампанию.")
        return

    save_template(company_id, campaign.campaign_id, wave_id, template_content, user_request, wave.subject)

    logger.info(f"[User {user_id}] Шаблон сохранён!")

    await message.reply("Шаблон успешно сохранён и привязан к волне!")
    # Уведомляем пользователя о начале генерации черновиков
    company = get_company_by_id(company_id)
    google_sheet_url = company.google_sheet_url if company and company.google_sheet_url else "Ссылка на таблицу не найдена"
    await message.reply(
        f"Начинаю генерацию черновиков. Это может занять до 15 минут.\n"
        f"📊 Google Таблица: {google_sheet_url}"
    )

    # Вызов функции генерации черновиков
    generated_drafts = await generate_drafts_for_wave(wave_id)

    # Проверяем, успешно ли сгенерировались черновики
    if generated_drafts:
        await message.reply("✅ Черновики успешно сгенерированы и добавлены в систему.")
    else:
        await message.reply("⚠️ Ошибка при генерации черновиков. Проверьте настройки и попробуйте снова.")

    await state.clear()

