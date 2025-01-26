from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram import types, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder

from agents.tempate_agent import async_template_edit_tool
from db.db import SessionLocal
from db.models import Waves, Templates, Campaigns, ChatThread
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


@router.message(TemplateStates.waiting_for_confirmation)
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон: сохраняет его или отправляет в режим редактирования.
    """
    user_id = message.from_user.id
    chat_id = message.chat.id
    state_data = await state.get_data()
    db = SessionLocal()

    logger.info(f"✅ [User {user_id}] Начал подтверждение шаблона...")

    try:
        if message.text.strip().lower() == "нет":
            await message.reply("✏️ Введите комментарии для изменения шаблона.")
            await state.set_state(TemplateStates.waiting_for_edit_input)  # Перевод в состояние редактирования
            return

        if message.text.strip().lower() != "да":
            await message.reply("⚠️ Пожалуйста, ответьте 'да' для подтверждения или 'нет' для редактирования.")
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
            wave_id=wave_id,
            subject=state_data["subject"],
            template_content=state_data["template_content"],
            user_request=state_data["user_request"],
        )

        db.add(new_template)
        db.commit()
        logger.info(f"✅ [User {user_id}] Шаблон сохранён! Тема: {state_data['subject']}, Волна: {wave_id}")

        await message.reply("✅ Шаблон успешно сохранён и привязан к волне!")
        await state.clear()

    except Exception as e:
        logger.error(f"❌ [User {user_id}] Ошибка при сохранении шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при сохранении шаблона. Попробуйте позже.")

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