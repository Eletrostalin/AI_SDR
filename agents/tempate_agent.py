import asyncio

from langchain.agents import Tool
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from promts.template_promt import template_generation_prompt, context_analysis_prompt, invite_prompt, \
    template_edit_prompt
from config import OPENAI_API_KEY
import logging


logger = logging.getLogger(__name__)

# Настройка LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0.7)

# Настройка инструментов
invite_chain = LLMChain(llm=llm, prompt=invite_prompt)
invite_tool = Tool(
    name="InviteTool",
    func=lambda: invite_chain.invoke({}),
    description="Просит пользователя ввести пожелания для шаблона."
)

context_analysis_chain = LLMChain(llm=llm, prompt=context_analysis_prompt)
context_analysis_tool = Tool(
    name="ContextAnalysis",
    func=context_analysis_chain.run,
    description="Анализирует ввод."
)

template_generation_chain = LLMChain(llm=llm, prompt=template_generation_prompt)
template_generation_tool = Tool(
    name="TemplateGenerator",
    func=template_generation_chain.run,
    description="Генерирует текст письма с учетом компании и контентного плана."
)

template_edit_chain = LLMChain(llm=llm, prompt=template_edit_prompt)
template_edit_tool = Tool(
    name="TemplateEditor",
    func=template_edit_chain.run,
    description="Редактирует текст шаблона на основе комментариев пользователя."
)

async def async_template_edit_tool(input_data: dict):
    """
    Асинхронно вызывает модель для редактирования шаблона.
    """
    return await asyncio.to_thread(template_edit_chain.run, input_data)

async def async_invite_tool():
    response = await asyncio.to_thread(invite_chain.invoke, {})

    # Проверяем, является ли ответ строкой или словарем
    if isinstance(response, dict):
        # Если это словарь, пробуем извлечь текст (обычно он в "text" или "content")
        response_text = response.get("text") or response.get("content") or str(response)
    else:
        response_text = str(response)  # Преобразуем в строку, если что-то пошло не так

    return response_text

async def async_context_analysis_tool(input_text: str):
    return await asyncio.to_thread(context_analysis_chain.run, {"input": input_text})

async def async_template_generation_tool(input_data: dict):
    return await asyncio.to_thread(template_generation_chain.run, input_data)
