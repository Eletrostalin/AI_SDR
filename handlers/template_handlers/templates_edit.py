from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram import types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder

from agents.tempate_agent import async_template_edit_tool
from db.db import SessionLocal
from db.models import Waves, Templates
from logger import logger
from states.states import TemplateStates

router = Router()

@router.callback_query(lambda c: c.data.startswith("edit_template:"))
async def start_edit_template(callback: CallbackQuery, state: FSMContext):
    """
    Начинает процесс редактирования шаблона.
    """
    wave_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    db = SessionLocal()

    logger.info(f"✏️ [User {user_id}] решил изменить шаблон для волны {wave_id}")

    try:
        # Получаем шаблон, связанный с волной
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave or not wave.template:
            await callback.message.reply("Шаблон для этой волны не найден.")
            return

        template = wave.template

        # Отправляем пользователю сообщение с инструкцией
        await callback.message.reply(
            f"✍️ Пожалуйста, напишите изменения, которые вы хотите внести в шаблон:\n\n"
            f"📌 **Тема:** {template.subject}\n"
            f"✉️ **Текст:** {template.template_content}\n\n"
            f"Просто напишите новый текст или укажите, что именно изменить."
        )

        # Сохраняем wave_id и шаблон в FSM
        await state.update_data(wave_id=wave_id, template_id=template.template_id)
        await state.set_state(TemplateStates.waiting_for_edit_input)

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при начале редактирования шаблона: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


@router.message(TemplateStates.waiting_for_edit_input)
async def handle_template_edit(message: types.Message, state: FSMContext):
    """
    Получает комментарии от пользователя, редактирует шаблон с помощью AI и показывает результат для подтверждения.
    """
    user_id = message.from_user.id
    db = SessionLocal()
    state_data = await state.get_data()

    wave_id = state_data.get("wave_id")
    template_id = state_data.get("template_id")
    user_comments = message.text.strip()

    logger.info(f"✏️ [User {user_id}] отправил комментарии для редактирования шаблона {template_id}: {user_comments[:100]}...")

    try:
        # Получаем шаблон из базы
        template = db.query(Templates).filter_by(template_id=template_id).first()
        if not template:
            await message.reply("Ошибка: шаблон не найден.")
            return

        # Подготавливаем данные для AI-редактирования
        edit_request = {
            "current_template": template.template_content,
            "comments": user_comments
        }

        # Запускаем AI-редактирование
        edited_template = await async_template_edit_tool(edit_request)

        if not edited_template or edited_template.strip() == "":
            await message.reply("⚠️ AI не смог сгенерировать новый текст. Попробуйте переформулировать комментарии.")
            return

        # Отправляем пользователю результат редактирования
        await message.reply(f"✍️ **Предлагаемый новый текст:**\n\n{edited_template}")

        # Спрашиваем пользователя, утверждает ли он изменения
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="✅ Да, сохранить", callback_data=f"confirm_edit:{template_id}"))
        keyboard.add(InlineKeyboardButton(text="✏️ Нет, изменить снова", callback_data=f"retry_edit:{template_id}"))

        await message.reply("Все ли верно? Вы можете утвердить изменения или ввести новые корректировки.", reply_markup=keyboard.as_markup())

        # Сохраняем новый текст в FSM, но пока **не записываем в базу**
        await state.update_data(edited_template=edited_template)

    except Exception as e:
        logger.error(f"❌ Ошибка при редактировании шаблона {template_id}: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


@router.callback_query(lambda c: c.data.startswith("confirm_edit:"))
async def confirm_template_edit(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждает и сохраняет измененный шаблон в базу данных.
    """
    user_id = callback.from_user.id
    state_data = await state.get_data()
    template_id = int(callback.data.split(":")[1])

    db = SessionLocal()

    try:
        # Получаем новый текст из FSM
        new_template_text = state_data.get("edited_template")

        # Проверяем, есть ли такой шаблон в базе
        template = db.query(Templates).filter_by(template_id=template_id).first()
        if not template:
            await callback.message.reply("Ошибка: шаблон не найден.")
            return

        # Обновляем текст шаблона в базе
        template.template_content = new_template_text
        db.commit()

        logger.info(f"✅ [User {user_id}] подтвердил и сохранил обновленный шаблон {template_id}.")

        # Отправляем пользователю подтверждение
        await callback.message.reply("✅ Шаблон успешно обновлён!")

        # Сбрасываем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении шаблона {template_id}: {e}", exc_info=True)
        await callback.message.reply("Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()


@router.callback_query(lambda c: c.data.startswith("retry_edit:"))
async def retry_template_edit(callback: CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю ввести новые комментарии для редактирования шаблона.
    """
    user_id = callback.from_user.id
    template_id = int(callback.data.split(":")[1])

    logger.info(f"✏️ [User {user_id}] хочет внести новые изменения в шаблон {template_id}.")

    await callback.message.reply("✍️ Введите новые корректировки для шаблона:")
    await state.set_state(TemplateStates.waiting_for_edit_input)