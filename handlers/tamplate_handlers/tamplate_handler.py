from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from handlers.campaign_handlers.campaign_handlers import router
from db.db_company import get_company_by_chat_id
from db.db_content_plan import get_campaign_by_thread_id
from db.models import Templates
from db.db import SessionLocal
import openai  # Функция взаимодействия с GPT
import logging

from promts.template_haandler import generate_email_template_prompt
from states.states import TemplateStates

logger = logging.getLogger(__name__)

@router.message(Command("add_template"))
async def start_template_creation(message: types.Message, state: FSMContext):
    """
    Начало создания шаблона.
    """
    db = SessionLocal()
    chat_id = str(message.chat.id)
    try:
        company = get_company_by_chat_id(db, chat_id)
        campaign = get_campaign_by_thread_id(db, chat_id)

        if not company or not campaign:
            await message.reply(
                "Компания или кампания не найдены. Убедитесь, что вы находитесь в правильном чате кампании."
            )
            return

        # Сохраняем данные о компании и кампании в состояние
        await state.update_data(
            company_id=company.company_id,
            campaign_id=campaign.campaign_id,
            company_info=company.info,  # Данные о компании
            campaign_name=campaign.campaign_name,
        )

        await message.reply("Введите описание или пожелания для шаблона.")
        await state.set_state(TemplateStates.waiting_for_description)
    finally:
        db.close()


@router.message(StateFilter(TemplateStates.waiting_for_description))
async def generate_template(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод описания или пожеланий пользователя.
    """
    user_request = message.text.strip()
    state_data = await state.get_data()
    company_info = state_data["company_info"]
    campaign_name = state_data["campaign_name"]

    # Генерация шаблона через GPT
    try:
        template_content = generate_email_template(
            company_info=company_info,
            campaign_name=campaign_name,
            user_request=user_request,
        )
        logger.debug(f"Сгенерированный шаблон: {template_content}")

        # Сохраняем данные в состояние
        await state.update_data(user_request=user_request, template_content=template_content)

        await message.reply(
            f"Вот предложенный шаблон:\n\n{template_content}\n\nУтвердить? (да/нет)"
        )
        await state.set_state(TemplateStates.waiting_for_confirmation)
    except Exception as e:
        logger.error(f"Ошибка при генерации шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при генерации шаблона. Попробуйте позже.")


@router.message(StateFilter(TemplateStates.waiting_for_confirmation))
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Обрабатывает подтверждение или отмену шаблона.
    """
    db = SessionLocal()
    try:
        if message.text.strip().lower() == "да":
            state_data = await state.get_data()
            company_id = state_data["company_id"]
            campaign_id = state_data["campaign_id"]
            user_request = state_data["user_request"]
            template_content = state_data["template_content"]

            # Сохраняем шаблон в базу данных
            new_template = Templates(
                company_id=company_id,
                campaign_id=campaign_id,
                user_request=user_request,
                template_content=template_content,
            )
            db.add(new_template)
            db.commit()

            await message.reply("Шаблон успешно сохранён!")
        else:
            await message.reply("Создание шаблона отменено.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при создании шаблона: {e}", exc_info=True)
        await message.reply("Произошла ошибка при сохранении шаблона.")
    finally:
        db.close()


def generate_email_template(company_info: str, campaign_name: str, user_request: str) -> str:
    """
    Генерирует шаблон письма с помощью OpenAI GPT.

    :param company_info: Информация о компании.
    :param campaign_name: Название кампании.
    :param user_request: Пожелания пользователя.
    :return: Сгенерированный текст шаблона.
    """
    # Используем функцию для получения текста промта
    prompt = generate_email_template_prompt(company_info, campaign_name, user_request)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Ошибка при генерации шаблона: {e}")