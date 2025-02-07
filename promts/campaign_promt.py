EMAIL_SEGMENT_COLUMNS = [
    "name", "region", "msp_registry", "director_name", "director_position",
    "phone_number", "email", "website", "primary_activity", "revenue", "employee_count"
]

CAMPAIGN_DATA_PROMPT = """
Анализируй текст: "{user_input}".
Извлеки следующие данные:
1. Дата начала (start_date) в формате ДД.ММ.ГГГГ. Если не указан год, подставь текущий. Если дата не ясна, оставь поле пустым.
2. Дата окончания (end_date) в формате ДД.ММ.ГГГГ. Если не указан год, подставь текущий. Если дата не ясна, оставь поле пустым.
3. Обязательные фильтры сегментации (filters) как словарь с ключами из списка:
"name", "region", "msp_registry", "director_name", "director_position", "phone_number", "email", "website", "primary_activity", "revenue", "employee_count"
4. Дополнительные параметры (params) как словарь.

Ответ должен быть строго в формате JSON. Если что-то невозможно определить, оставь поле пустым. Пример:
{{
    "start_date": "15.06.2023",
    "end_date": "",
    "filters": {{"region": "Москва", "status": "active"}},
    "params": {{"goal": "увеличение продаж"}}
}}
"""