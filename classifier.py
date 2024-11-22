import openai
import logging
import json
from config import OPENAI_API_KEY
from client import client

logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY

BASE_PROMPT = """
Ты помощник для классификации пользовательских запросов. Твоя задача — анализировать текст и определять два параметра:
1. Тип действия (action_type): возможные значения: "add", "edit", "delete", "view".
2. Тип сущности (entity_type): возможные значения: "company", "template", "email_table", "content_plan".

Если в тексте не удалось однозначно определить действие или сущность, верни:
{{
  "action_type": "unknown",
  "entity_type": "unknown"
}}.

Примеры:
- "Добавить новую кампанию": {{"action_type": "add", "entity_type": "company"}}
- "Удалить шаблон": {{"action_type": "delete", "entity_type": "template"}}
- "Хочу контент план на месяц": {{"action_type": "view", "entity_type": "content_plan"}}
- "Непонятный запрос": {{"action_type": "unknown", "entity_type": "unknown"}}

Теперь проанализируй следующий текст: {input_text}
"""


async def classify_message(message_text: str) -> dict:
    try:
        logger.debug("Отправка запроса в OpenAI...")

        prompt = BASE_PROMPT.format(input_text=message_text)

        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        logger.debug(f"Полный ответ от OpenAI: {response}")

        content = response.choices[0].message.content
        logger.debug(f"Ответ модели (content): {content}")

        result = json.loads(content.strip())
        return result
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}", exc_info=True)
        return {"action_type": "error", "entity_type": None}