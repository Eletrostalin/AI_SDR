from datetime import timedelta, datetime

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.exc import SQLAlchemyError

from agents.tempate_agent import async_invite_tool
from db.db import SessionLocal
from db.models import Templates, Waves, Company, CompanyInfo, ContentPlan, Campaigns, ChatThread
from promts.template_promt import generate_email_prompt
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
    db = SessionLocal()
    chat_id = str(message.chat.id)
    thread_id = message.message_thread_id

    try:
        logger.info(f"[User {message.from_user.id}] Запуск add_template, thread_id={thread_id}")

        # Получаем кампанию по thread_id
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            await message.reply("Кампания, связанная с этим чатом, не найдена.")
            logger.warning(f"Кампания не найдена для thread_id={thread_id}")
            return

        logger.debug(f"Найдена кампания: {campaign.campaign_id} ({campaign.campaign_name})")

        # Получаем компанию, связанную с кампанией
        company = db.query(Company).filter_by(company_id=campaign.company_id).first()
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
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign.campaign_id).all()
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
        keyboard = InlineKeyboardBuilder()
        for content_plan in content_plans:
            keyboard.add(InlineKeyboardButton(
                text=content_plan.description or f"Контент-план {content_plan.content_plan_id}",
                callback_data=f"select_content_plan:{content_plan.content_plan_id}"
            ))

        await message.reply("Выберите контентный план:", reply_markup=keyboard.as_markup())

    except Exception as e:
        logger.error(f"Ошибка при инициализации шаблона: {e}", exc_info=True)
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

        # Сохраняем контент-план в FSM
        await state.update_data(content_plan_id=content_plan.content_plan_id, content_plan_desc=content_plan.description)

        logger.debug(f"✅ Контент-план сохранен в FSMContext: {content_plan.content_plan_id}")

        # Отправляем выбор волн
        keyboard = InlineKeyboardBuilder()
        for wave in waves:
            keyboard.add(InlineKeyboardButton(
                text=f"{wave.subject} ({wave.send_date.strftime('%Y-%m-%d')})",
                callback_data=f"select_wave:{wave.wave_id}"
            ))

        await callback.message.reply("Выберите волну рассылки:", reply_markup=keyboard.as_markup())

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

    logger.debug(f"⚡ Выбрана волна ID: {wave_id}")

    db = SessionLocal()
    try:
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            await callback.message.reply("Выбранная волна не найдена.")
            return

        # Проверяем, что дата волны не раньше завтрашнего дня
        today = datetime.now().date()
        wave_date = wave.send_date.date()
        if wave_date < today + timedelta(days=1):
            await callback.message.reply(
                "❌ Ошибка: Вы не можете выбрать дату раньше завтрашнего дня.\n"
                "📅 Пожалуйста, выберите новую дату отправки."
            )
            return  # Оставляем пользователя в том же состоянии

        await state.update_data(wave_id=wave_id)  # Убрали subject, так как он больше не нужен

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
        await callback.message.reply("❌ Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


async def handle_user_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод пользователя и вызывает AI-ассистента для генерации шаблона.
    """
    user_input = message.text.strip()
    chat_id = str(message.chat.id)
    db = SessionLocal()

    try:
        state_data = await state.get_data()
        company_id = state_data.get("company_id")
        content_plan_id = state_data.get("content_plan_id")

        if not company_id:
            company = db.query(Company).filter_by(chat_id=chat_id).first()
            if company:
                company_id = company.company_id
                await state.update_data(company_id=company_id)
            else:
                await message.reply("Ошибка: компания не найдена.")
                return

        if not content_plan_id:
            await message.reply("Ошибка: не удалось найти контент-план.")
            return

        # Запрашиваем данные компании и контент-плана
        company_data = (
            db.query(CompanyInfo, ContentPlan.description)
            .join(ContentPlan, CompanyInfo.company_id == ContentPlan.company_id)
            .filter(CompanyInfo.company_id == company_id, ContentPlan.content_plan_id == content_plan_id)
            .first()
        )

        if not company_data:
            await message.reply("Ошибка: не удалось найти данные компании или контент-план.")
            return

        company_info, content_plan_desc = company_data

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

        # Генерируем промпт
        prompt = generate_email_prompt(company_details)

        # Отправляем запрос в модель
        template_response = send_to_model(prompt)

        if not template_response:
            await message.reply("Ошибка при генерации шаблона. Попробуйте позже.")
            return

        await state.update_data(template_content=template_response)

        # Отправляем пользователю сгенерированный шаблон
        await message.reply(f"Сгенерированный шаблон:\n\n{template_response}\n\nПодтвердите? (да/нет)")
        await state.set_state(TemplateStates.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка при генерации шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при генерации шаблона. Попробуйте позже.")

    finally:
        db.close()


@router.message(TemplateStates.waiting_for_confirmation)
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон и сохраняет его в БД.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    state_data = await state.get_data()
    db = SessionLocal()

    logger.info(f"✅ [User {user_id}] Начал подтверждение шаблона...")

    try:
        # Если пользователь не подтвердил шаблон, запрашиваем новый промт
        if message.text.strip().lower() != "да":
            await message.reply("Попробуйте снова. Введите новый запрос для генерации шаблона.")
            logger.info(f"❌ [User {user_id}] Отклонил шаблон. Ожидание нового ввода.")

            # Переводим состояние в ожидание нового user_request
            await state.set_state(TemplateStates.waiting_for_description)
            return

        # **Логируем текущее состояние**
        logger.debug(f"📌 Содержимое FSM перед проверкой: {state_data}")

        # Проверяем, что есть все нужные данные
        required_fields = ["company_id", "template_content", "user_request", "wave_id"]
        missing_fields = [field for field in required_fields if field not in state_data]

        if missing_fields:
            logger.warning(f"⚠️ [User {user_id}] Отсутствуют данные: {missing_fields}")

            # **Попытка восстановить user_request**
            if "user_request" in missing_fields:
                last_message = await state.get_state()
                if last_message:
                    await state.update_data(user_request=last_message)
                    logger.info(f"🔄 Восстановлен user_request: {last_message}")

            # Проверяем снова после восстановления
            state_data = await state.get_data()
            missing_fields = [field for field in required_fields if field not in state_data]
            if missing_fields:
                logger.error(f"❌ [User {user_id}] Критическая ошибка: данные по-прежнему отсутствуют {missing_fields}")
                await message.reply("Ошибка: отсутствуют внутренние данные. Попробуйте снова.")
                return

        company_id = state_data["company_id"]
        wave_id = state_data["wave_id"]
        template_content = state_data["template_content"]
        user_request = state_data["user_request"]

        # **Получаем subject из waves**
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            logger.error(f"❌ [User {user_id}] Ошибка: не удалось найти волну с wave_id={wave_id}")
            await message.reply("Ошибка: не удалось найти волну. Попробуйте снова.")
            return

        subject = wave.subject  # Используем subject из waves

        # **Проверяем наличие кампании**
        chat_thread = db.query(ChatThread).filter_by(chat_id=chat_id).first()
        if not chat_thread:
            logger.error(f"❌ [User {user_id}] ChatThread не найден для chat_id: {chat_id}")
            await message.reply("Ошибка: не удалось найти кампанию.")
            return

        campaign = db.query(Campaigns).filter_by(thread_id=chat_thread.thread_id).first()
        if not campaign:
            logger.error(f"❌ [User {user_id}] Кампания не найдена для thread_id: {chat_thread.thread_id}")
            await message.reply("Ошибка: не удалось найти кампанию.")
            return

        # ✅ Создаём шаблон
        new_template = Templates(
            company_id=company_id,
            campaign_id=campaign.campaign_id,
            wave_id=wave_id,
            template_content=template_content,
            user_request=user_request,
            subject=subject,  # Используем subject из wave
        )

        db.add(new_template)
        db.commit()
        logger.info(f"✅ [User {user_id}] Шаблон сохранён! Subject: {subject}, Волна: {wave_id}")

        await message.reply("Шаблон успешно сохранён и привязан к волне!")
        await state.clear()

    except SQLAlchemyError as e:
        logger.error(f"❌ [User {user_id}] Ошибка при сохранении шаблона: {e}", exc_info=True)
        await message.reply("Ошибка при сохранении шаблона. Попробуйте позже.")

    finally:
        db.close()
