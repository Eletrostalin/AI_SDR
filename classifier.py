from openai import OpenAI
import json
from config import OPENAI_API_KEY
from promts.base_promt import BASE_PROMPT
from promts.campaign_promt import CREATE_CAMPAIGN_PROMPT
from promts.company_promt import PROCESS_COMPANY_INFORMATION_PROMPT
from states.states import AddCampaignState
from logger import logger

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def classify_message(message_text: str) -> dict:
    """
    Классифицирует пользовательское сообщение, используя OpenAI.
    """
    try:
        logger.debug("Starting message classification...")

        # Проверяем, что message_text не None и не пустой
        if not message_text or not message_text.strip():
            logger.warning("Received empty or None message text for classification.")
            return {"action_type": "unknown", "entity_type": "unknown"}

        # Escape curly braces in the message text
        escaped_text = message_text.replace("{", "{{").replace("}", "}}")

        # Format the prompt with the escaped message text
        prompt = BASE_PROMPT.format(input_text=escaped_text)
        #logger.debug(f"Formatted prompt: {prompt}")

        # Call the OpenAI API
        logger.debug("Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Log the full response from the model
        #logger.debug(f"Full response from OpenAI: {response}")

        # Extract the content from the response
        content = response.choices[0].message.content.strip()
        #logger.debug(f"Model response content: {content}")

        # Clean the content by removing any prefixes like "Ответ:"
        if content.lower().startswith("ответ:"):
            content = content.split(":", 1)[1].strip()

        # Attempt to parse the content as JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError as parse_error:
            logger.error(f"JSON parsing error: {parse_error}")
            logger.debug(f"Invalid JSON content: {content}")
            result = {"action_type": "unknown", "entity_type": "unknown"}

        return result
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {e}", exc_info=True)
        return {"action_type": "unknown", "entity_type": "unknown"}

def extract_company_data(company_text: str) -> dict:
    """
    Извлекает данные о компании из текста, используя OpenAI.
    """
    try:
        # Форматируем промпт
        prompt = PROCESS_COMPANY_INFORMATION_PROMPT.format(input_text=company_text)
        logger.debug(f"Formatted company prompt: {prompt}")

        # Вызываем OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Извлекаем и парсим ответ
        content = response.choices[0].message.content
        logger.debug(f"Company data response: {content}")
        return json.loads(content.strip())
    except json.JSONDecodeError as json_error:
        logger.error(f"JSON parsing error: {json_error}", exc_info=True)
        return {"error": "Invalid JSON response from model"}
    except Exception as e:
        logger.error(f"Error extracting company data: {e}", exc_info=True)
        return {"error": str(e)}

async def extract_campaign_data_with_validation(input_text: str, state, message):
    """
    Извлекает данные о кампании из текста, используя OpenAI, с сохранением частичных данных.
    """
    try:
        # Форматируем промпт
        prompt = CREATE_CAMPAIGN_PROMPT.format(input_text=input_text)
        logger.debug(f"Formatted campaign prompt: {prompt}")

        # Вызываем OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Извлекаем и парсим ответ
        content = response.choices[0].message.content
        logger.debug(f"Campaign data response: {content}")
        campaign_data = json.loads(content.strip())

        # Проверяем данные
        campaign_name = campaign_data.get("campaign_name")
        if not campaign_name or campaign_name.strip() == "":
            # Если название не извлечено, сохраняем частичные данные и запрашиваем название
            logger.warning("Название кампании отсутствует. Запрашиваем у пользователя.")
            await state.update_data(partial_campaign_data=campaign_data)
            await message.reply("Не удалось определить название кампании. Укажите его.")
            await state.set_state(AddCampaignState.waiting_for_campaign_name)
            return None

        # Возвращаем полные данные
        return campaign_data

    except json.JSONDecodeError as json_error:
        logger.error(f"JSON parsing error: {json_error}", exc_info=True)
        await message.reply("Ошибка обработки данных кампании. Попробуйте снова.")
        return None
    except Exception as e:
        logger.error(f"Error extracting campaign data: {e}", exc_info=True)
        await message.reply("Произошла ошибка. Пожалуйста, повторите запрос.")
        return None
