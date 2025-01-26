from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session

from db.db import SessionLocal
from db.models import Templates, Waves, ContentPlan, Campaigns

import logging

from states.states import TemplateStates

logger = logging.getLogger(__name__)
router = Router()


# 📌 1. Команда /delete_template - начинаем процесс удаления шаблона
@router.message(Command("delete_template"))
async def delete_template(message: types.Message, state: FSMContext):
    """
    Начинает процесс удаления шаблона. Предлагает пользователю выбрать контент-план.
    """
    db = SessionLocal()
    thread_id = message.message_thread_id  # Определяем thread_id
    user_id = message.from_user.id

    logger.info(f"🗑️ [User {user_id}] отправил команду /delete_template в теме {thread_id}")

    try:
        # Получаем кампанию по thread_id
        campaign = db.query(Campaigns).filter_by(thread_id=thread_id).first()
        if not campaign:
            await message.reply("Кампания, связанная с этим чатом, не найдена.")
            return

        # Получаем список контент-планов для этой кампании
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign.campaign_id).all()

        if not content_plans:
            await message.reply("Для этой кампании нет доступных контентных планов.")
            return

        # Создаем инлайн-кнопки для выбора контентного плана
        keyboard = InlineKeyboardBuilder()
        for content_plan in content_plans:
            keyboard.add(InlineKeyboardButton(
                text=content_plan.description or f"Контент-план {content_plan.content_plan_id}",
                callback_data=f"delete_content_plan:{content_plan.content_plan_id}"
            ))

        # Отправляем пользователю выбор
        await message.reply("Выберите контент-план для удаления шаблона:", reply_markup=keyboard.as_markup())

        # Сохраняем campaign_id в состояние
        await state.update_data(campaign_id=campaign.campaign_id)

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при получении контент-планов: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте позже.")
    finally:
        db.close()


# 📌 2. Выбор волны контент-плана
@router.callback_query(lambda c: c.data.startswith("delete_content_plan:"))
async def delete_content_plan(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор контент-плана и предлагает выбрать волну.
    """
    content_plan_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"📌 [User {user_id}] выбрал контент-план {content_plan_id} для удаления шаблона")

    try:
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
                callback_data=f"delete_wave:{wave.wave_id}"
            ))

        # Отправляем пользователю выбор волн
        await callback.message.reply("Выберите волну, шаблон которой хотите удалить:", reply_markup=keyboard.as_markup())

        # Сохраняем content_plan_id в FSM
        await state.update_data(content_plan_id=content_plan_id)

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при выборе контент-плана {content_plan_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


# 📌 3. Подтверждение удаления шаблона
@router.callback_query(lambda c: c.data.startswith("delete_wave:"))
async def delete_wave(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор волны, показывает шаблон и запрашивает подтверждение удаления.
    """
    wave_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"🗑️ [User {user_id}] выбрал волну {wave_id} для удаления шаблона")

    try:
        # Получаем волну и связанный с ней шаблон
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave or not wave.template:
            await callback.message.reply("Для этой волны шаблон не найден.")
            return

        template = wave.template

        # Отправляем пользователю шаблон и запрашиваем подтверждение удаления
        template_message = (
            f"📩 **Удаление шаблона**\n\n"
            f"📌 **Тема:** {template.subject}\n\n"
            f"✉️ **Текст письма:**\n{template.template_content}"
        )
        await callback.message.reply(template_message)

        # Кнопки подтверждения
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_template:{template.template_id}"))
        keyboard.add(InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete"))

        await callback.message.reply("Вы уверены, что хотите удалить этот шаблон?", reply_markup=keyboard.as_markup())

        # Сохраняем wave_id и template_id в FSM
        await state.update_data(wave_id=wave_id, template_id=template.template_id)
        await state.set_state(TemplateStates.waiting_for_delete_confirmation)

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении шаблона {wave_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


# 📌 4. Подтверждение удаления шаблона
@router.callback_query(lambda c: c.data.startswith("confirm_delete_template:"))
async def confirm_delete_template(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждает удаление шаблона (мягкое удаление: status = False).
    """
    template_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"✅ [User {user_id}] подтвердил удаление шаблона {template_id}")

    try:
        # Обновляем статус шаблона (мягкое удаление)
        template = db.query(Templates).filter_by(template_id=template_id).first()
        if not template:
            await callback.message.reply("Шаблон не найден.")
            return

        template.status = False
        db.commit()

        await callback.message.reply("✅ Шаблон успешно удалён!")

        # Сбрасываем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"❌ Ошибка при удалении шаблона {template_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


# 📌 5. Отмена удаления
@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    """
    Отмена удаления шаблона.
    """
    await callback.message.reply("Удаление отменено.")
    await state.clear()