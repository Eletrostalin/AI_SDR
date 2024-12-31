from aiogram import Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from langchain.agents import Tool, create_structured_chat_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
import json
import logging

from db.db import SessionLocal
from db.models import CompanyInfo
from states.states import OnboardingState

router = Router()
logger = logging.getLogger(__name__)

# Инструменты для агента
def get_onboarding_tools():
    def validate_email(input_text):
        import re
        return re.match(r"[^@]+@[^@]+\.[^@]+", input_text)

    def validate_phone(input_text):
        import re
        return re.match(r"^\+?[0-9\s\-\(\)]+$", input_text)

    tools = [
        Tool(
            name="company_name",
            func=lambda x: x.strip(),
            description="Скажите, как называется ваша компания."
        ),
        Tool(
            name="industry",
            func=lambda x: x.strip(),
            description="В какой сфере работает ваша компания?"
        ),
        Tool(
            name="region",
            func=lambda x: x.strip(),
            description="Укажите регион, в котором работает компания."
        ),
        Tool(
            name="contact_email",
            func=lambda x: x.strip() if validate_email(x) else "Некорректный email.",
            description="Какой email лучше использовать для связи?"
        ),
        Tool(
            name="contact_phone",
            func=lambda x: x.strip() if validate_phone(x) else "Некорректный номер телефона.",
            description="Укажите контактный телефон компании."
        ),
        Tool(
            name="additional_info",
            func=lambda x: x.strip() if x else "Пропустить.",
            description="Есть ли дополнительные данные, которые вы хотели бы указать?"
        ),
    ]
    return tools

def create_onboarding_agent():
    """
    Создает агента для онбординга с использованием LangChain.
    """
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
    tools = get_onboarding_tools()

    # Генерируем описание инструментов
    tools_description = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])

    system_prompt = f"""
Вы виртуальный ассистент, который помогает компаниям пройти процесс онбординга. 
Ваша задача — извлечь из текста пользователя данные по следующим категориям:
- Название компании (company_name)
- Сфера деятельности (industry)
- Регион (region)
- Контактный email (contact_email)
- Контактный телефон (contact_phone)
- Дополнительная информация (additional_info)

Вы можете использовать инструменты для извлечения данных. Доступные инструменты:
{tools_description}

Инструменты принимают входные данные в формате JSON с ключами:
- "action": имя инструмента
- "action_input": входные данные для инструмента.

Если информация не найдена, задайте уточняющий вопрос пользователю. Используйте вежливые формулировки.

Пример вызова инструмента:
{{
  "action": "company_name",
  "action_input": "Коннектед"
}}

Отвечайте четко, учтиво, и используйте инструменты только при необходимости.
"""

    # Создаем шаблон промпта
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),  # Добавлено для учета scratchpad
    ])

    # Создаем агента
    return create_structured_chat_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )

# Обработчик состояния
@router.message(StateFilter(OnboardingState.waiting_for_first_response))
async def handle_onboarding_message(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает сообщение пользователя и заполняет данные.
    """
    try:
        chat_id = message.chat.id
        text = message.text

        # Создаем агента
        agent = create_onboarding_agent()

        # Получаем сохраненные данные
        collected_data = await state.get_data()
        required_fields = [
            "company_name", "industry", "region", "contact_email", "contact_phone", "additional_info"
        ]

        # Вызываем агента
        response = agent.invoke({"input": text})

        # Логируем результат
        logger.info(f"Ответ агента: {response}")

        # Извлекаем данные из ответа
        for message_data in response["messages"]:
            if isinstance(message_data, dict) and message_data.get("content"):
                try:
                    result = json.loads(message_data["content"])
                    field = result.get("action")
                    value = result.get("action_input")
                    if field in required_fields:
                        collected_data[field] = value
                except json.JSONDecodeError:
                    logger.error("Ошибка декодирования JSON из ответа инструмента.")

        # Проверяем, какие данные отсутствуют
        incomplete_fields = [field for field in required_fields if not collected_data.get(field)]

        if not incomplete_fields:
            # Все данные собраны
            summary = "\n".join([f"{key}: {value}" for key, value in collected_data.items()])
            await bot.send_message(chat_id, f"Все данные успешно собраны:\n{summary}")
            await state.clear()
        else:
            # Уточняем недостающие данные
            for field in incomplete_fields:
                description = next((tool.description for tool in get_onboarding_tools() if tool.name == field), field)
                await bot.send_message(chat_id, f"Пожалуйста, уточните: {description}")
            await state.update_data(**collected_data)

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await bot.send_message(chat_id, "Произошла ошибка. Попробуйте еще раз.")