from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from langchain.prompts import PromptTemplate
from langchain.agents import AgentExecutor, Tool
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from db.db import SessionLocal
from db.models import CompanyInfo
from aiogram.types import Message
import logging

from states.states import OnboardingState

router = Router()
logger = logging.getLogger(__name__)

# Инструменты для агента
def get_onboarding_tools():
    """
    Определяем инструменты для сбора информации о компании.
    """
    def validate_email(input_text):
        import re
        return re.match(r"[^@]+@[^@]+\.[^@]+", input_text)

    def validate_phone(input_text):
        import re
        return re.match(r"^\+?[0-9\s\-\(\)]+$", input_text)

    tools = [
        Tool(
            name="company_name",
            func=lambda input_text: input_text.strip(),
            description="Собрать название компании."
        ),
        Tool(
            name="industry",
            func=lambda input_text: input_text.strip(),
            description="Собрать сферу деятельности компании."
        ),
        Tool(
            name="region",
            func=lambda input_text: input_text.strip(),
            description="Собрать регион компании."
        ),
        Tool(
            name="contact_email",
            func=lambda input_text: input_text.strip() if validate_email(input_text) else "Некорректный email.",
            description="Собрать контактный email компании."
        ),
        Tool(
            name="contact_phone",
            func=lambda input_text: input_text.strip() if validate_phone(input_text) else "Некорректный номер телефона.",
            description="Собрать контактный телефон компании."
        ),
        Tool(
            name="additional_info",
            func=lambda input_text: input_text.strip() if input_text else "Пропустить",
            description="Собрать дополнительные данные о компании."
        ),
    ]
    return tools

# Создаем агента LangChain
def create_onboarding_agent():
    """
    Создает агента для онбординга с LangChain.
    """
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    tools = get_onboarding_tools()

    prompt = PromptTemplate(
        input_variables=["chat_history", "input"],
        template=(
            "Ты помощник для сбора информации о компании. Используй доступные инструменты "
            "для уточнения данных. Если данные уже собраны, уточни оставшиеся.\n"
            "{chat_history}\n\n"
            "Входящее сообщение: {input}\n"
        )
    )

    return AgentExecutor.from_agent_and_tools(
        agent="zero-shot-react-description",
        tools=tools,
        llm=llm,
        memory=memory,
        verbose=True,
        prompt=prompt,
    )

@router.message(state=OnboardingState.waiting_for_first_response)
async def handle_first_response(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает первый ответ пользователя после приветственного сообщения.
    """
    try:
        chat_id = message.chat.id
        text = message.text  # Ответ пользователя

        # Передаем текст в онбординг-агент
        await handle_onboarding_with_agent(chat_id=chat_id, text=text, bot=bot)

        # Сбрасываем состояние
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка обработки первого ответа: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего ответа. Попробуйте снова.")

# Обработчик для онбординга
async def handle_onboarding_with_agent(chat_id: int, text: str, bot: Bot):
    """
    Управление онбордингом с помощью агента LangChain, с передачей параметров напрямую.
    """
    db = SessionLocal()
    try:
        agent = create_onboarding_agent()

        # Загружаем предыдущие данные (если есть)
        company_data = db.query(CompanyInfo).filter_by(chat_id=str(chat_id)).first()
        collected_data = {
            "company_name": company_data.company_name if company_data else None,
            "industry": company_data.industry if company_data else None,
            "region": company_data.region if company_data else None,
            "contact_email": company_data.contact_email if company_data else None,
            "contact_phone": company_data.contact_phone if company_data else None,
            "additional_info": company_data.additional_info if company_data else None,
        }

        # Проверяем, какие данные отсутствуют
        incomplete_fields = [key for key, value in collected_data.items() if not value]

        # Если все данные собраны
        if not incomplete_fields:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "Все данные собраны:\n"
                    f"📌 Название компании: {collected_data['company_name']}\n"
                    f"📌 Сфера деятельности: {collected_data['industry']}\n"
                    f"📌 Регион: {collected_data['region']}\n"
                    f"📌 Email: {collected_data['contact_email']}\n"
                    f"📌 Телефон: {collected_data['contact_phone']}\n"
                    f"📌 Дополнительно: {collected_data['additional_info']}\n\n"
                    "Если хотите обновить данные, отправьте новые значения."
                )
            )
            return

        # Если есть недостающие данные
        result = agent.run(input=text)

        # Логируем результат
        logger.info(f"Агент собрал данные: {result}")

        # Сохраняем данные
        for field, value in result.items():
            if field in collected_data:
                collected_data[field] = value

        # Обновляем или создаем запись в базе
        if company_data:
            for field, value in collected_data.items():
                setattr(company_data, field, value)
        else:
            company_data = CompanyInfo(chat_id=str(chat_id), **collected_data)
            db.add(company_data)

        db.commit()

        # Уведомляем пользователя
        await bot.send_message(chat_id=chat_id, text=f"Данные обновлены: {result}")

    except Exception as e:
        logger.error(f"Ошибка онбординга: {e}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text="Произошла ошибка. Попробуйте снова.")
    finally:
        db.close()