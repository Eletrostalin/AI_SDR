CAMPAIGN_DATA_PROMPT = '''
Ты – аналитик данных. Разбери текст: "{user_input}" и извлеки следующие данные:

1. **Дата начала** (start_date) – в формате "ДД.ММ.ГГГГ". Если не указан год, подставь текущий. Если дата отсутствует, оставь поле пустым.  
2. **Дата окончания** (end_date) – в формате "ДД.ММ.ГГГГ". Если не указан год, подставь текущий. Если дата отсутствует, оставь поле пустым.  
3. **Фильтры сегментации** (filters) – словарь с ключами **ТОЛЬКО** из списка:  
   - "name", "tax_id", "registration_date", "address", "region", "status",  
   - "msp_registry", "director_name", "director_position", "phone_number",  
   - "email", "website", "primary_activity", "other_activities", "licenses",  
   - "revenue", "balance", "net_profit_or_loss", "arbitration_defendant",  
   - "employee_count", "branch_count".  

**Формат значений в filters**:  
- **Строковые параметры** ("region", "status") – либо `true` (если любой регион/статус), либо список значений (например, `["Москва", "СПб"]`).  
- **Числовые параметры** ("employee_count", "revenue") – либо `{{">": 1000}}` (означает "больше 1000"), либо конкретное число, например `1000000`.  
- **Логические параметры** ("email", "phone_number", "licenses") – `true`, если параметр обязателен, `false`, если не учитывать.  

**Пример правильного JSON-ответа**:  
{{
    "start_date": "15.06.2023",
    "end_date": "30.06.2023",
    "filters": {{
        "region": ["Москва", "Санкт-Петербург"],
        "employee_count": {{">": 500}},
        "email": true,
        "director_name": true
    }}
}}
'''