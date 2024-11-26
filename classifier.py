from openai import OpenAI
import logging
import json
from config import OPENAI_API_KEY
from promts.base_promt import BASE_PROMPT

logger = logging.getLogger(__name__)

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def classify_message(message_text: str) -> dict:
    try:
        logger.debug("Starting message classification...")

        # Escape curly braces in the message text
        escaped_text = message_text.replace("{", "{{").replace("}", "}}")

        # Format the prompt with the escaped message text
        prompt = BASE_PROMPT.format(input_text=escaped_text)
        logger.debug(f"Formatted prompt: {prompt}")

        # Call the OpenAI API
        logger.debug("Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )

        # Log the full response from the model
        logger.debug(f"Full response from OpenAI: {response}")

        # Extract the content from the response
        content = response.choices[0].message.content
        logger.debug(f"Model response content: {content}")

        # Attempt to parse the content as JSON
        try:
            result = json.loads(content.strip())
        except json.JSONDecodeError as parse_error:
            logger.error(f"JSON parsing error: {parse_error}")
            logger.debug(f"Invalid JSON content: {content}")
            result = {"action_type": "unknown", "entity_type": "unknown"}

        return result
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {e}", exc_info=True)
        return {"action_type": "error", "entity_type": None}