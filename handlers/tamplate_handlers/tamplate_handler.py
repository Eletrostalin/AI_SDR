from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from sqlalchemy.orm import Session
from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from db.db import SessionLocal
from db.models import Templates, Waves, Company, CompanyInfo
from states.states import TemplateStates
from config import OPENAI_API_KEY
import json
import logging

logger = logging.getLogger(__name__)
router = Router()

# Настройка LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.7)

# Инструмент для первого запроса данных
invite_prompt = ChatPromptTemplate.from_template("""
Пожалуйста, введите основные пожелания для шаблона письма.
Например:
- Цель письма (продажа, информирование и т.д.).
- Целевая аудитория.
- Особенности тона письма (дружелюбный, формальный и т.д.).
""")
invite_chain = LLMChain(llm=llm, prompt=invite_prompt)
invite_tool = Tool(name="InviteTool", func=invite_chain.run, description="Запрашивает данные для шаблона.")

# Инструмент для анализа пользовательского ввода
context_analysis_prompt = ChatPromptTemplate.from_template("""
Мы ожидаем текст с пожеланиями для шаблона письма. Текст: {input}

Если текст соответствует ожиданиям, ответь "valid".
Если текст не соответствует, ответь "invalid" и кратко объясни, почему.
""")
context_analysis_chain = LLMChain(llm=llm, prompt=context_analysis_prompt)
context_analysis_tool = Tool(name="ContextAnalysis", func=context_analysis_chain.run, description="Анализирует ввод.")

# Инструмент для генерации текста письма
template_generation_prompt = ChatPromptTemplate.from_template("""
Сгенерируй текст письма на основе данных:
- Тема письма: {subject}
- Цель письма: {goal}
- Целевая аудитория: {audience}
- Тональность: {tone}

Пожелания пользователя:
{user_request}

Ответь в виде текста письма, включая приветствие, основной текст и заключение.
""")
template_generation_chain = LLMChain(llm=llm, prompt=template_generation_prompt)
template_generation_tool = Tool(name="TemplateGenerator", func=template_generation_chain.run,
                                description="Генерирует текст письма.")


@router.message(Command("add_template"))
async def add_template(message: types.Message, state: FSMContext):
    """
    Инициализирует процесс создания шаблона.
    """
    db = SessionLocal()
    chat_id = str(message.chat.id)

    try:
        # Получаем компанию по chat_id
        company = db.query(Company).filter_by(chat_id=chat_id).first()
        if not company:
            await message.reply("Компания для данного чата не найдена.")
            return

        # Получаем волну (Wave) для компании
        wave = db.query(Waves).filter_by(company_id=company.company_id).first()
        if not wave:
            await message.reply("Волна с темой письма для данной компании не найдена.")
            return

        subject = wave.subject

        # Сохраняем данные в состояние FSM
        await state.update_data(
            company_id=company.company_id,
            campaign_id=wave.campaign_id,
            subject=subject,
        )

        # Генерация приглашения для ввода данных
        invite_message = invite_tool.run({})
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
    Обрабатывает ввод пользователя.
    """
    user_input = message.text.strip()

    # Анализ пользовательского ввода
    analysis_response = context_analysis_tool.run({"input": user_input})
    analysis_data = json.loads(analysis_response)

    if analysis_data["status"] == "invalid":
        await message.reply(f"Некорректный ввод: {analysis_data['reason']}\nПопробуйте снова.")
        return

    # Если ввод валиден, добавляем данные в состояние
    await state.update_data(user_request=user_input)

    # Генерация текста письма
    state_data = await state.get_data()
    template_response = template_generation_tool.run({
        "subject": state_data["subject"],
        "goal": analysis_data.get("goal", "информирование"),
        "audience": analysis_data.get("audience", "широкая аудитория"),
        "tone": analysis_data.get("tone", "дружелюбный"),
        "user_request": user_input,
    })

    # Сохраняем текст шаблона в состояние
    await state.update_data(template_content=template_response)

    # Отправляем шаблон пользователю
    await message.reply(f"Сгенерированный шаблон:\n\n{template_response}\n\nПодтвердите? (да/нет)")
    await state.set_state(TemplateStates.waiting_for_confirmation)


@router.message(StateFilter(TemplateStates.waiting_for_confirmation))
async def confirm_template(message: types.Message, state: FSMContext):
    """
    Подтверждает или отклоняет шаблон.
    """
    if message.text.strip().lower() == "да":
        db = SessionLocal()
        try:
            state_data = await state.get_data()

            # Сохраняем шаблон в базу
            new_template = Templates(
                company_id=state_data["company_id"],
                campaign_id=state_data["campaign_id"],
                subject=state_data["subject"],
                template_content=state_data["template_content"],
                user_request=state_data["user_request"],
            )
            db.add(new_template)
            db.commit()

            await message.reply("Шаблон успешно сохранён!")
            await state.clear()
        except Exception as e:
            logger.error(f"Ошибка при сохранении шаблона: {e}")
            await message.reply("Произошла ошибка при сохранении шаблона.")
        finally:
            db.close()
    elif message.text.strip().lower() == "нет":
        # Если шаблон отклонён, запросить уточнения
        await message.reply(
            "Пожалуйста, уточните, что нужно изменить в шаблоне.\n"
            "Например: изменить тональность, добавить информацию, исправить структуру и т.д."
        )
        await state.set_state(TemplateStates.refining_template)
    else:
        await message.reply("Пожалуйста, ответьте 'да' или 'нет'.")


@router.message(StateFilter(TemplateStates.refining_template))
async def refine_template(message: types.Message, state: FSMContext):
    """
    Обрабатывает уточнения пользователя для изменения шаблона.
    """
    user_feedback = message.text.strip()
    state_data = await state.get_data()

    try:
        # Генерация нового шаблона с учетом пожеланий
        refined_template = template_generation_tool.run({
            "subject": state_data["subject"],
            "goal": "информирование",  # Можно оставить фиксированное значение или извлекать из state_data
            "audience": "широкая аудитория",
            "tone": "дружелюбный",  # Можно сделать тональность настраиваемой
            "user_request": f"{state_data['user_request']}\n\n{user_feedback}",
        })

        # Обновление состояния с новым шаблоном
        await state.update_data(template_content=refined_template)

        # Отправка нового шаблона пользователю
        await message.reply(
            f"Вот обновленный шаблон:\n\n{refined_template}\n\nПодтвердите? (да/нет)"
        )
        await state.set_state(TemplateStates.waiting_for_confirmation)

    except Exception as e:
        logger.error(f"Ошибка при доработке шаблона: {e}")
        await message.reply("Произошла ошибка при доработке шаблона. Попробуйте позже.")