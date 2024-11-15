import openai
import logging
import json  # Для обработки JSON
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY

# Промпт для модели с экранированными скобками
BASE_PROMPT = """
Ты помощник для классификации пользовательских запросов. Твоя задача — анализировать текст и определять два параметра:
1. Тип действия (action_type): возможные значения: "add", "edit", "delete", "view".
2. Тип сущности (entity_type): возможные значения: "campaign", "template", "email_table", "content_plan".

Если в тексте не удалось однозначно определить действие или сущность, верни:
{{
  "action_type": "unknown",
  "entity_type": "unknown"
}}.

Примеры:
- "Добавить новую кампанию": {{"action_type": "add", "entity_type": "campaign"}}
- "Удалить шаблон": {{"action_type": "delete", "entity_type": "template"}}
- "Хочу контент план на месяц": {{"action_type": "view", "entity_type": "content_plan"}}
- "Непонятный запрос": {{"action_type": "unknown", "entity_type": "unknown"}}

Теперь проанализируй следующий текст: {input_text}
"""

def classify_message(message_text: str) -> dict:
    try:
        logger.debug("Отправка запроса в OpenAI...")

        # Экранируем текст сообщения
        def escape_message_text(message_text: str) -> str:
            return message_text.replace("{", "{{").replace("}", "}}")

        # Формируем запрос с промптом
        escaped_text = escape_message_text(message_text)
        prompt = BASE_PROMPT.format(input_text=escaped_text)
        logger.debug(f"Сформированный промпт: {prompt}")

        # Логируем параметры вызова OpenAI
        logger.debug("Вызов OpenAI API...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Логируем весь ответ от модели
        logger.debug(f"Полный ответ от OpenAI: {response}")

        # Извлекаем текст ответа
        content = response['choices'][0]['message']['content']
        logger.debug(f"Ответ модели (content): {content}")

        # Попытка очистить и обработать JSON
        try:
            normalized_content = content.strip()
            if normalized_content.startswith("{") and normalized_content.endswith("}"):
                result = json.loads(normalized_content)
            else:
                raise json.JSONDecodeError("Ответ не начинается с JSON-объекта.", normalized_content, 0)
        except json.JSONDecodeError as parse_error:
            logger.error(f"Ошибка парсинга JSON: {parse_error}")
            logger.debug(f"Невалидный JSON: {content}")
            result = {"action_type": "unknown", "entity_type": "unknown"}

        return result
    except Exception as e:
        logger.error(f"Ошибка при обращении к OpenAI: {e}", exc_info=True)
        return {"action_type": "error", "entity_type": None}