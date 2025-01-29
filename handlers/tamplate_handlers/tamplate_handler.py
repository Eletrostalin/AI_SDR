from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from sqlalchemy.orm import Session
from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from db.db import SessionLocal
from db.models import Templates, Waves, Company, CompanyInfo, ContentPlan
from states.states import TemplateStates
from config import OPENAI_API_KEY
import json
import logging


logger = logging.getLogger(__name__)
router = Router()

# Настройка LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.7)

# 1. Инструмент для запроса данных у пользователя
invite_prompt = ChatPromptTemplate.from_template("""
Ты AI-ассистент. Попроси пользователя тактично ввести пожелания для генерации шаблонов письма. 
Формулируй просьбу по-разному каждый раз, чтобы пользователь не замечал однотипности.
Отвечай только одной строкой текста без дополнительных структур JSON или метаданных.
""")
invite_chain = LLMChain(llm=llm, prompt=invite_prompt)
invite_tool = Tool(
    name="InviteTool",
    func=lambda: invite_chain.invoke({}),  # Теперь invoke() и без аргументов
    description="Просит пользователя ввести пожелания для шаблона."
)

# 2. Инструмент для анализа пользовательского ввода
context_analysis_prompt = ChatPromptTemplate.from_template("""
Мы ожидаем текст с пожеланиями для шаблона письма. Текст: {input}

Если текст соответствует ожиданиям, ответь "valid".
Если текст не соответствует, ответь "invalid" и кратко объясни, почему.
""")
context_analysis_chain = LLMChain(llm=llm, prompt=context_analysis_prompt)
context_analysis_tool = Tool(
    name="ContextAnalysis",
    func=context_analysis_chain.run,
    description="Анализирует ввод."
)

# 3. Инструмент для генерации текста письма (использует данные компании и контентного плана)
template_generation_prompt = ChatPromptTemplate.from_template("""
Сгенерируй текст письма для компании "{company_name}" (сфера: {industry}, регион: {region}).

Контентный план: {content_plan}
Тема письма: {subject}
Цель письма: {goal}
Целевая аудитория: {audience}
Тональность: {tone}

Пожелания пользователя:
{user_request}

Ответь в виде письма с приветствием, основным текстом и заключением.
""")
template_generation_chain = LLMChain(llm=llm, prompt=template_generation_prompt)
template_generation_tool = Tool(
    name="TemplateGenerator",
    func=template_generation_chain.run,
    description="Генерирует текст письма с учетом компании и контентного плана."
)

# Обработчик команды /add_template
@router.message(Command("add_template"))
async def add_template(message: types.Message, state: FSMContext):
    """
    Запускает процесс создания шаблона.
    """
    db = SessionLocal()
    chat_id = str(message.chat.id)

    try:
        # Получаем компанию по chat_id
        company = db.query(Company).filter_by(chat_id=chat_id).first()
        if not company:
            await message.reply("Компания для данного чата не найдена.")
            return

        # Получаем данные о компании из CompanyInfo
        company_info = db.query(CompanyInfo).filter_by(company_id=company.company_id).first()
        if not company_info:
            await message.reply("Информация о компании не найдена.")
            return

        # Получаем текущую волну (Wave) для компании
        wave = db.query(Waves).filter_by(company_id=company.company_id).first()
        if not wave:
            await message.reply("Волна с темой письма для данной компании не найдена.")
            return

        # Получаем описание контентного плана
        content_plan = db.query(ContentPlan).filter_by(company_id=company.company_id).first()
        content_plan_desc = content_plan.description if content_plan else "Нет данных"

        subject = wave.subject

        # Сохраняем данные в FSM
        await state.update_data(
            company_name=company_info.company_name,
            industry=company_info.industry,
            region=company_info.region,
            contact_email=company_info.contact_email,
            contact_phone=company_info.contact_phone or "Не указан",
            additional_info=company_info.additional_info or "Нет дополнительной информации",
            subject=subject,
            content_plan=content_plan_desc,
        )

        # Генерируем сообщение-приглашение
        try:
            invite_response = invite_tool.func()
            invite_message = (
                invite_response["text"]
                if isinstance(invite_response, dict) and "text" in invite_response
                else invite_response
            )
        except Exception as lc_error:
            logger.error(f"Ошибка при генерации приглашения: {lc_error}")
            await message.reply("Не удалось сгенерировать приглашение. Попробуйте позже.")
            return

        await message.reply(invite_message)
        await state.set_state(TemplateStates.waiting_for_description)

    except Exception as e:
        logger.error(f"Ошибка при инициализации шаблона: {e}")
        await message.reply("Произошла ошибка при инициализации. Попробуйте позже.")
    finally:
        db.close()


@router.message(StateFilter(TemplateStates.waiting_for_description))
async def handle_user_input(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод пользователя и сразу переходит к генерации шаблона.
    """
    user_input = message.text.strip()

    logger.debug(f"Получен пользовательский ввод: {user_input}")

    # ❌ Убрана проверка через ContextAnalysis

    # Устанавливаем стандартные параметры
    analysis_data = {
        "goal": "информирование",
        "audience": "широкая аудитория",
        "tone": "дружелюбный"
    }

    # Сохранение данных в состояние
    await state.update_data(user_request=user_input)

    # Достаем из состояния данные компании
    state_data = await state.get_data()

    logger.debug(f"Данные перед генерацией шаблона: {state_data}")

    # Генерация текста письма
    template_response = template_generation_tool.invoke({
        "input": {
            "company_name": state_data["company_name"],
            "industry": state_data["industry"],
            "region": state_data["region"],
            "content_plan": state_data["content_plan"],
            "subject": state_data["subject"],
            "goal": analysis_data["goal"],
            "audience": analysis_data["audience"],
            "tone": analysis_data["tone"],
            "user_request": user_input,
        }
    })

    logger.debug(f"Сгенерированный шаблон: {template_response}")

    # Сохранение результата
    await state.update_data(template_content=template_response)

    # Отправка пользователю
    await message.reply(f"Сгенерированный шаблон:\n\n{template_response}\n\nПодтвердите? (да/нет)")
    await state.set_state(TemplateStates.waiting_for_confirmation)


@router.message(TemplateStates.waiting_for_confirmation)
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон.
    """
    if message.text.strip().lower() == "да":
        state_data = await state.get_data()
        db = SessionLocal()

        # Получаем компанию по имени из состояния
        company_info = db.query(CompanyInfo).filter_by(company_name=state_data["company_name"]).first()
        if not company_info:
            await message.reply("Ошибка: не удалось найти компанию по сохраненному имени.")
            return

        company_id = company_info.company_id

        # Получаем кампанию для компании
        campaign = db.query(Waves).filter_by(company_id=company_id).first()
        campaign_id = campaign.campaign_id if campaign else None

        new_template = Templates(
            company_id=company_id,
            campaign_id=campaign_id,
            subject=state_data["subject"],
            template_content=state_data["template_content"],
            user_request=state_data["user_request"],
        )

        db.add(new_template)
        db.commit()
        db.close()

        await message.reply("Шаблон успешно сохранён!")
        await state.clear()
    else:
        await message.reply("Попробуйте снова.")
