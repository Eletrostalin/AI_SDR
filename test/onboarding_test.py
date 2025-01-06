import json
import logging
from langchain_core.messages import HumanMessage

# Подключаем необходимые функции из модуля
from handlers.onboarding_handler import create_onboarding_agent

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def run_onboarding_console():
    """
    Тестирование процесса онбординга через консоль.
    """
    try:
        # Инициализируем агента
        agent = create_onboarding_agent()

        # Начальное сообщение
        print("Добро пожаловать в процесс онбординга!")
        print("Введите данные о вашей компании. Вы можете начать с любого поля, например: 'Моя компания называется ExampleCorp'.")

        # Симуляция процесса
        collected_data = {
            "company_name": None,
            "industry": None,
            "region": None,
            "contact_email": None,
            "contact_phone": None,
            "additional_info": None,
        }

        while True:
            # Пользовательский ввод
            user_input = input("Вы: ")

            # Пользователь хочет завершить процесс
            if user_input.lower() in ["стоп", "выход", "quit", "exit"]:
                print("Опрос завершен. Спасибо за участие!")
                break

            # Передаем сообщение в агента
            response = agent.invoke({"input": user_input})

            # Логируем результат
            logger.debug(f"Ответ агента: {response}")

            # Извлекаем и обновляем собранные данные
            for message_data in response["messages"]:
                if isinstance(message_data, dict) and message_data.get("content"):
                    try:
                        result = json.loads(message_data["content"])
                        field = result.get("action")
                        value = result.get("action_input")
                        if field in collected_data:
                            collected_data[field] = value
                    except json.JSONDecodeError:
                        logger.error("Ошибка декодирования JSON из ответа инструмента.")

            # Проверяем, есть ли незаполненные поля
            incomplete_fields = [field for field, value in collected_data.items() if not value]

            if not incomplete_fields:
                # Все данные собраны
                print("Все данные успешно собраны. Спасибо!")
                print("Собранные данные:")
                for key, value in collected_data.items():
                    print(f"- {key}: {value}")
                break
            else:
                # Сообщаем пользователю, что еще нужно
                print("Для завершения предоставьте следующие данные:")
                for field in incomplete_fields:
                    print(f"- {field}")

    except Exception as e:
        logger.error(f"Ошибка во время тестирования: {e}", exc_info=True)
        print("Произошла ошибка. Попробуйте снова.")

if __name__ == "__main__":
    run_onboarding_console()