EMAIL_SEGMENT_COLUMNS = [
    "name", "region","msp_registry", "director_name", "director_position",
    "phone_number", "email", "website", "primary_activity", "revenue", "employee_count",
    "branch_count"
]

# Фиксированные фильтры и их возможные типы
FILTER_TYPES = {
    "name": ["str"],  # Название компании - всегда строка
    "region": ["list", "bool", "str"],  # ["Москва", "СПб"] или True (любой регион)
    "msp_registry": ["bool"],  # True (есть в реестре) / False (нет)
    "director_name": ["bool", "str"],  # True (должен быть указан) или конкретное ФИО
    "director_position": ["str"],  # Должность директора - строка
    "phone_number": ["bool", "str"],  # True (должен быть) или конкретный номер
    "email": ["bool", "str"],  # True (должен быть) или конкретный email
    "website": ["bool", "str"],  # True (должен быть) или конкретный URL
    "primary_activity": ["str"],  # Основной вид деятельности - строка
    "revenue": ["dict", "int", "bool"],  # {">": 1000000}, 1000000 или True (любая выручка)
    "employee_count": ["dict", "int", "bool"],  # {">": 500}, 500 или True
}
