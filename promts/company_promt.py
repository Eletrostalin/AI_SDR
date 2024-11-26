PROCESS_COMPANY_INFORMATION_PROMPT = """
Извлеки данные о компании из следующей информации:
{input_text}

Верни их в формате JSON:
{{
    "company_name": "Название компании",
    "industry": "Сфера деятельности",
    "description": "Описание"
}}
"""