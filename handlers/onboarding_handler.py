from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session

from config import OPENAI_API_KEY
from db.db import SessionLocal
from db.models import CompanyInfo
from promts.onboarding_promt import NEUTRAL_REFINEMENT_PROMPT, FIRST_QUESTION_PROMPT, EXTRACTOR_PROMPT
from states.states import OnboardingState
from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json
import logging

logger = logging.getLogger(__name__)
router = Router()

# Инициализация OpenAI модели
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.7)

# Настройка инструментов LangChain
extractor_prompt = ChatPromptTemplate.from_template(EXTRACTOR_PROMPT)
extractor_chain = LLMChain(llm=llm, prompt=extractor_prompt)
extractor_tool = Tool(name="Extractor", func=extractor_chain.run, description="Извлекает сущности из текста")

first_question_prompt = ChatPromptTemplate.from_template(FIRST_QUESTION_PROMPT)
first_question_chain = LLMChain(llm=llm, prompt=first_question_prompt)
first_question_tool = Tool(name="FirstQuestionGenerator", func=first_question_chain.run,
                           description="Генерирует первый запрос к пользователю")

neutral_refinement_prompt = ChatPromptTemplate.from_template(NEUTRAL_REFINEMENT_PROMPT)
neutral_question_chain = LLMChain(llm=llm, prompt=neutral_refinement_prompt)
neutral_question_tool = Tool(name="NeutralQuestionGenerator", func=neutral_question_chain.run,
                             description="Генерирует уточняющий запрос")


@router.message(OnboardingState.waiting_for_company_name)
async def handle_company_name(message: Message, state: FSMContext):
    """
    Обработка названия компании через LangChain.
    """
    extracted_response = extractor_tool.run({"input": message.text})
    data = json.loads(extracted_response)
    await state.update_data(data=data)

    # Проверяем недостающие поля
    missing_fields = [field for field, value in data.items() if not value and field != "additional_info"]

    if not missing_fields:
        await state.set_state(OnboardingState.showing_collected_data)
        await show_collected_data(message, state)
    else:
        await state.update_data(missing_fields=missing_fields)
        question = first_question_tool.run({"missing_fields": ", ".join(missing_fields)})
        await message.answer(question)
        await state.set_state(OnboardingState.waiting_for_missing_data)


@router.message(OnboardingState.waiting_for_missing_data)
async def handle_missing_data(message: Message, state: FSMContext):
    """
    Уточнение недостающих данных через LangChain.
    """
    data = await state.get_data()
    missing_fields = data.get("missing_fields", [])

    logger.debug(f"Текущие данные перед уточнением: {data}")

    # Повторное извлечение данных
    refined_response = extractor_tool.run({"input": message.text})
    refined_data = json.loads(refined_response)

    # Обновляем данные состояния
    for field in missing_fields:
        if refined_data.get(field):
            data[field] = refined_data[field]

    # Проверяем оставшиеся недостающие поля
    missing_fields = [field for field in missing_fields if not data.get(field)]
    await state.update_data(data)
    await state.update_data(missing_fields=missing_fields)

    logger.debug(f"Обновленные данные после уточнения: {data}")

    if not missing_fields:
        logger.debug("Все данные собраны. Переходим к подтверждению.")
        await state.set_state(OnboardingState.showing_collected_data)
        await show_collected_data(message, state)
    else:
        question = neutral_question_tool.run({"missing_fields": ", ".join(missing_fields)})
        await message.answer(question)


async def show_collected_data(message: Message, state: FSMContext):
    """
    Отображение собранных данных пользователю для подтверждения.
    """
    data = await state.get_data()

    # Проверяем наличие данных
    logger.debug(f"Данные для отображения пользователю: {data}")

    summary = (
        f"Пожалуйста, подтвердите собранные данные:\n\n"
        f"Название компании: {data.get('company_name', 'Не указано')}\n"
        f"Сфера деятельности: {data.get('industry', 'Не указано')}\n"
        f"Регион работы: {data.get('region', 'Не указано')}\n"
        f"Email: {data.get('contact_email', 'Не указано')}\n"
        f"Телефон: {data.get('contact_phone', 'Не указано')}\n"
        f"Дополнительная информация: {data.get('additional_info', 'Не указано')}\n\n"
        f"Если все верно, напишите 'Да'. Если есть ошибка, напишите 'Нет'."
    )
    await message.answer(summary)
    await state.set_state(OnboardingState.confirmation)


@router.message(OnboardingState.confirmation)
async def handle_confirmation(message: Message, state: FSMContext):
    """
    Подтверждение данных компании.
    """
    data = await state.get_data()
    logger.debug(f"Данные для подтверждения: {data}")

    if message.text.lower() == "да":
        company_id = data.get("company_id")

        # Генерация числового company_id, если он отсутствует
        if not company_id:
            logger.warning("company_id отсутствует, создаем новый.")
            company_id = int(f"{abs(message.chat.id)}{int(message.date.timestamp())}")
            data["company_id"] = company_id
            await state.update_data(company_id=company_id)

        db: Session = SessionLocal()
        try:
            # Проверяем, существует ли запись с данным company_id
            existing_company = db.query(CompanyInfo).filter_by(company_id=company_id).first()
            if existing_company:
                logger.info(f"Компания с ID {company_id} уже существует, обновляем данные.")
                existing_company.company_name = data.get("company_name")
                existing_company.industry = data.get("industry")
                existing_company.region = data.get("region")
                existing_company.contact_email = data.get("contact_email")
                existing_company.contact_phone = data.get("contact_phone")
                existing_company.additional_info = data.get("additional_info")
            else:
                logger.info(f"Создаем новую запись для компании с ID {company_id}.")
                company_info = CompanyInfo(
                    company_id=company_id,
                    company_name=data.get("company_name"),
                    industry=data.get("industry"),
                    region=data.get("region"),
                    contact_email=data.get("contact_email"),
                    contact_phone=data.get("contact_phone"),
                    additional_info=data.get("additional_info"),
                )
                db.add(company_info)

            db.commit()
            logger.info("Данные компании успешно сохранены в базу данных.")

            await message.answer(
                "🎉 Данные компании успешно сохранены! Теперь вы можете начать работу с ботом.\n"
                "Напишите 'Помощь', чтобы узнать, что я могу делать."
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения данных компании: {e}", exc_info=True)
            await message.answer("Произошла ошибка при сохранении данных. Попробуйте снова.")
        finally:
            db.close()

        await state.clear()
        logger.debug("Состояние пользователя очищено.")
    else:
        logger.info("Пользователь отклонил подтверждение данных.")
        await state.set_state(OnboardingState.waiting_for_company_name)
        await message.answer("Опрос начат заново. Введите название вашей компании.")