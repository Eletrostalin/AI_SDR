EMAIL_SEGMENT_COLUMNS = [
    "name", "tax_id", "registration_date", "address", "region", "status",
    "msp_registry", "director_name", "director_position", "phone_number",
    "email", "website", "primary_activity", "other_activities", "licenses",
    "revenue", "balance", "net_profit_or_loss", "arbitration_defendant",
    "employee_count", "branch_count"
]

# Фиксированные фильтры и их возможные типы
FILTER_TYPES = {
    "name": ["str"],  # Название компании - всегда строка
    "tax_id": ["str"],  # ИНН - строка (может содержать лидирующие нули)
    "registration_date": ["str", "dict"],  # Дата: "2022-01-01" или {">": "2020-01-01"}
    "address": ["str"],  # Адрес - строка
    "region": ["list", "bool", "str"],  # ["Москва", "СПб"] или True (любой регион)
    "status": ["str"],  # Статус компании - строка
    "msp_registry": ["bool"],  # True (есть в реестре) / False (нет)
    "director_name": ["bool", "str"],  # True (должен быть указан) или конкретное ФИО
    "director_position": ["str"],  # Должность директора - строка
    "phone_number": ["bool", "str"],  # True (должен быть) или конкретный номер
    "email": ["bool", "str"],  # True (должен быть) или конкретный email
    "website": ["bool", "str"],  # True (должен быть) или конкретный URL
    "primary_activity": ["str"],  # Основной вид деятельности - строка
    "other_activities": ["str"],  # Дополнительные виды деятельности - строка
    "licenses": ["bool"],  # True (есть лицензия) / False (нет)
    "revenue": ["dict", "int", "bool"],  # {">": 1000000}, 1000000 или True (любая выручка)
    "balance": ["dict", "int", "bool"],  # {">": 500000}, 500000 или True
    "net_profit_or_loss": ["dict", "int", "bool"],  # {">": 0}, 10000 или True
    "arbitration_defendant": ["bool"],  # True (есть арбитражные дела) / False (нет)
    "employee_count": ["dict", "int", "bool"],  # {">": 500}, 500 или True
    "branch_count": ["dict", "int", "bool"],  # {">": 3}, 3 или True
}
