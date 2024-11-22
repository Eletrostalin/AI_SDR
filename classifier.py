import openai
import logging
import json
from config import OPENAI_API_KEY
from client import client
from promts.base_promt import BASE_PROMPT

logger = logging.getLogger(__name__)
openai.api_key = OPENAI_API_KEY

BASE_PROMPT = BASE_PROMPT


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