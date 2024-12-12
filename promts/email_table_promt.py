EMAIL_SEGMENT_COLUMNS = [
    "name", "tax_id", "registration_date", "address", "region", "status",
    "msp_registry", "director_name", "director_position", "phone_number",
    "email", "website", "primary_activity", "other_activities", "licenses",
    "revenue", "balance", "net_profit_or_loss", "arbitration_defendant",
    "employee_count", "branch_count"
]


def generate_column_mapping_prompt(user_columns: list) -> str:
    """
    Формирует текстовый промпт для сопоставления колонок.

    :param user_columns: Список колонок, загруженных из файла пользователя.
    :return: Текстовый промпт.
    """
    return (
        f"У нас есть таблица с колонками: {', '.join(EMAIL_SEGMENT_COLUMNS)}.\n"
        f"Пользователь загрузил таблицу с колонками: {', '.join(user_columns)}.\n"
        f"Твоя задача — сопоставить колонки пользователя с нашими колонками.\n"
        f"Названия могут быть разными, например: 'Электронный адрес' и 'Email' это одно и то же.\n"
        f"Верни результат в формате JSON, где ключ — это колонка пользователя, а значение — наша колонка. "
        f"Если колонка пользователя не найдена, укажи null."
    )