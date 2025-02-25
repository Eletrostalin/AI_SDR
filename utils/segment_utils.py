import json
import logging

from db.segmentation import FILTER_TYPES
from utils.utils import send_to_model, logger  # Функция отправки в модель

def extract_filters_from_text(user_input: str) -> dict:
    """
    Отправляет текст пользователя в модель и получает список фильтров в фиксированном формате.
    """
    prompt = f"""
    Ты – аналитик данных. Определи фильтры сегментации из текста пользователя.
    Используй ТОЛЬКО следующие поля: {list(FILTER_TYPES.keys())}

    **Твой ответ должен быть в JSON-формате**, где:
    - Значения должны соответствовать возможным типам данных (число, строка, булево значение или список).
    - Если параметр просто упоминается (например, "есть email"), ставь `true`.
    - Если в тексте есть операторы сравнения (`больше 500`, `менее 100`), записывай их как `{{"<": 100}}`.
    - Если фильтр включает несколько значений (например, "по Москве и Санкт-Петербургу"), используй список.

    **Примеры:**
    1️⃣ Вход: "Фильтрация по Москве и у кого есть телефон"
       Ответ:
       {{
         "filters": {{
           "region": ["Москва"],
           "phone_number": true
         }}
       }}

    2️⃣ Вход: "Компании с числом сотрудников больше 500"
       Ответ:
       {{
         "filters": {{
           "employee_count": {{">": 500}}
         }}
       }}

    3️⃣ Вход: "Все, у кого есть лицензия и больше 10 филиалов"
       Ответ:
       {{
         "filters": {{
           "licenses": true,
           "branch_count": {{">": 10}}
         }}
       }}

    4️⃣ Вход: "{user_input}"
       Ответ:
    """

    logger.debug(f"🔹 Отправляем в модель:\n{prompt}")

    response = send_to_model(prompt)
    logger.debug(f"📥 Ответ модели: {response}")

    # Парсим JSON-ответ
    try:
        model_data = json.loads(response)
        filters = model_data.get("filters", {})

        # Проверяем корректность данных
        validated_filters = {}
        for key, value in filters.items():
            if key in FILTER_TYPES:
                expected_types = FILTER_TYPES[key]

                # Проверяем bool
                if isinstance(value, bool) and "bool" in expected_types:
                    validated_filters[key] = value

                # Проверяем список строк
                elif isinstance(value, list) and all(isinstance(i, str) for i in value) and "list" in expected_types:
                    validated_filters[key] = value

                # Проверяем число + оператор
                elif isinstance(value, dict) and all(
                        isinstance(v, (int, str)) for v in value.values()) and "dict" in expected_types:
                    validated_filters[key] = value

                # Если что-то не так — логируем и пропускаем
                else:
                    logger.warning(f"⚠️ Пропущен неподходящий формат: {key} → {value}")

        logger.info(f"✅ Итоговые фильтры: {validated_filters}")
        return validated_filters

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ Ошибка обработки JSON: {e}")
        return {}

def generate_segment_table_name(company_id: int) -> str:
    """
    Генерирует имя таблицы на основе ID компании.

    :param company_id: ID компании.
    :return: Сформированное имя таблицы.
    """
    return f"table_{company_id}"