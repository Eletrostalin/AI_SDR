from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, CallbackQuery, message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session

from db.db import SessionLocal
from db.models import Templates, Waves, ContentPlan, Campaigns

import logging

from states.states import TemplateStates

logger = logging.getLogger(__name__)
router = Router()

# 📌 1. Команда /view_templates - Выбираем контент-план
@router.message(Command("view_templates"))
async def view_templates(message: types.Message, state: FSMContext):
    """
    Начинает процесс просмотра шаблонов. Показывает список контент-планов кампании.
    """
    db = SessionLocal()
    thread_id = message.message_thread_id  # Определяем thread_id
    user_id = message.from_user.id

    logger.info(f"👤 [User {user_id}] отправил команду /view_templates в теме {thread_id}")

    try:
        # Получаем кампанию по thread_id
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            await message.reply("Кампания, связанная с этим чатом, не найдена.")
            return

        # Получаем список контент-планов для этой кампании
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign.campaign_id).all()

        if not content_plans:
            await message.reply("Для этой кампании нет доступных контент-планов.")
            return

        # Создаем инлайн-кнопки для выбора контентного плана
        keyboard = InlineKeyboardBuilder()
        for content_plan in content_plans:
            keyboard.add(InlineKeyboardButton(
                text=content_plan.description or f"Контент-план {content_plan.content_plan_id}",
                callback_data=f"view_content_plan:{content_plan.content_plan_id}"
            ))

        # Отправляем пользователю выбор
        await message.reply("Выберите контентный план для просмотра шаблонов:", reply_markup=keyboard.as_markup())

        # Логируем сохраненные данные
        logger.info(f"✅ [User {user_id}] Кампания {campaign.campaign_id} найдена. Показываем контент-планы.")

        # Сохраняем campaign_id в состояние
        await state.update_data(
            campaign_id=campaign.campaign_id
        )

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при получении контент-планов: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


# 📌 2. Выбор волны контент-плана
@router.callback_query(lambda c: c.data.startswith("view_content_plan:"))
async def view_content_plan(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор контент-плана и предлагает выбрать волну.
    """
    content_plan_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"📌 [User {user_id}] выбрал контент-план {content_plan_id}")

    try:
        # Получаем контент-план
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
                callback_data=f"view_wave:{wave.wave_id}"
            ))

        # Отправляем пользователю выбор волн
        await callback.message.reply("Выберите волну для просмотра шаблона:", reply_markup=keyboard.as_markup())

        # Логируем сохраненные данные
        logger.info(f"✅ [User {user_id}] Контент-план {content_plan_id} содержит {len(waves)} волн.")

        # Сохраняем content_plan_id в FSM
        await state.update_data(content_plan_id=content_plan_id)

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при выборе контент-плана {content_plan_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


# 📌 3. Запрос шаблона для выбранной волны
@router.callback_query(lambda c: c.data.startswith("view_wave:"))
async def view_wave(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор волны и отправляет шаблон пользователю.
    """
    wave_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"🌊 [User {user_id}] выбрал волну {wave_id}")

    try:
        # Получаем волну
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            await callback.message.reply("Выбранная волна не найдена.")
            return

        # Получаем шаблон через связь (правильный способ)
        if not wave.template:
            await callback.message.reply("Для этой волны шаблон не найден.")
            return

        template = wave.template

        # Логируем шаблон перед отправкой
        logger.info(f"📄 [User {user_id}] Просматривает шаблон:\n"
                    f"📌 Тема: {template.subject}\n"
                    f"✉️ Текст: {template.template_content[:100]}...")  # Логируем только первые 100 символов

        # Отправляем пользователю шаблон
        template_message = (
            f"📩 **Шаблон письма**\n\n"
            f"📌 **Тема:** {template.subject}\n\n"
            f"✉️ **Текст письма:**\n{template.template_content}"
        )
        await callback.message.reply(template_message)
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="✏️ Да, изменить", callback_data=f"edit_template:{wave_id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Нет", callback_data="cancel_edit"))

        await callback.message.reply("Все ли верно? Вы можете утвердить изменения или ввести новые корректировки.", reply_markup=keyboard.as_markup())

        # Сохраняем wave_id в FSM
        await state.update_data(wave_id=wave_id)
    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при просмотре шаблона для волны {wave_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()