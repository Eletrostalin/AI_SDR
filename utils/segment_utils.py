import json

from sqlalchemy.sql import text
import os
from sqlalchemy.orm import Session
import pandas as pd

from db.segmentation import EMAIL_SEGMENT_COLUMNS
from utils.utils import send_to_model, logger  # Функция отправки в модель


def extract_filters_from_text(user_input: str) -> dict:
    """
    Отправляет текст пользователя в модель и получает список фильтров в фиксированном формате.
    """
    # Создаём промпт с явным указанием доступных фильтров
    prompt = f"""
    Ты – аналитик данных. Определи фильтры сегментации из текста пользователя.
    Используй ТОЛЬКО следующие поля: {EMAIL_SEGMENT_COLUMNS}

    **Твой ответ должен быть в JSON-формате**, где:
    - Ключи соответствуют доступным фильтрам сегментации.
    - Значения могут быть булевыми (`true`/`false`), числами (`int`), строками (`str`) или списками (`list`).
    - Если параметр просто упоминается (например, "есть email"), ставь `true`.
    - Если в тексте есть операторы (`больше 500`, `менее 100`), записывай их как `{{"<": 100}}`.
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

    3️⃣ Вход: "{user_input}"
       Ответ:
    """

    response = send_to_model(prompt)  # Отправляем в GPT
    logger.debug(f"📥 Ответ модели: {response}")

    # Обрабатываем JSON-ответ
    try:
        model_data = json.loads(response)
        filters = model_data.get("filters", {})

        if not isinstance(filters, dict):
            raise ValueError("Модель вернула некорректные данные (ожидался словарь).")

        # Валидация данных: отбираем только разрешённые фильтры
        validated_filters = {}
        for key, value in filters.items():
            if key in EMAIL_SEGMENT_COLUMNS:  # Проверяем, что фильтр допустим
                if isinstance(value, (bool, str, int, list, dict)):  # Проверяем тип данных
                    validated_filters[key] = value
                else:
                    logger.warning(f"⚠️ Пропущен неподходящий формат: {key} → {value}")

        logger.info(f"✅ Итоговые фильтры: {validated_filters}")
        return validated_filters

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"❌ Ошибка обработки JSON: {e}")
        return {}  # Возвращаем пустой словарь при ошибке


def apply_filters_to_email_table(db: Session, email_table_id: int, filters: dict) -> pd.DataFrame:
    """
    Применяет фильтры к email-таблице и возвращает отфильтрованный DataFrame.

    :param db: Сессия базы данных.
    :param email_table_id: ID email-таблицы.
    :param filters: Фильтры сегментации.
    :return: DataFrame с отфильтрованными email-лидами.
    """
    try:
        # Определяем название email-таблицы
        query_table = text("SELECT table_name FROM email_tables WHERE email_table_id = :email_table_id")
        result = db.execute(query_table, {"email_table_id": email_table_id}).fetchone()

        if not result:
            logger.error(f"❌ Email-таблица с ID {email_table_id} не найдена.")
            return pd.DataFrame()

        table_name = result[0]
        logger.info(f"📌 Используем email-таблицу: {table_name}")

        # Загружаем данные
        query_data = f"SELECT * FROM {table_name}"
        df = pd.read_sql(query_data, db.bind)

        if df.empty:
            logger.warning(f"⚠️ Таблица {table_name} пуста.")
            return pd.DataFrame()

        logger.debug(f"🔍 Загружено {len(df)} записей из таблицы {table_name}")
        logger.debug(f"📋 Доступные колонки: {df.columns.tolist()}")

        # Вывод уникальных значений для всех колонок, которые есть в фильтрах
        for key in filters.keys():
            if key in df.columns:
                unique_values = df[key].dropna().unique()
                logger.debug(f"📌 Уникальные значения в колонке '{key}': {unique_values}")

        # Применяем фильтры
        for key, value in filters.items():
            if key in df.columns:
                # Приводим текстовые данные к единому формату
                if df[key].dtype == "object":
                    df[key] = df[key].astype(str).str.strip().str.lower()

                # 🔹 **Обрабатываем `true` и `false` как наличие/отсутствие значений**
                if isinstance(value, str) and value.lower() == "true":
                    df = df[df[key].notna() & (df[key] != "")]
                elif isinstance(value, str) and value.lower() == "false":
                    df = df[df[key].isna() | (df[key] == "")]
                elif isinstance(value, dict):  # Фильтрация по операторам >, <
                    for op, val in value.items():
                        if op == ">":
                            df = df[df[key] > val]
                        elif op == "<":
                            df = df[df[key] < val]
                elif isinstance(value, list):  # Фильтр по списку значений
                    normalized_values = [v.lower().strip() for v in value]
                    df = df[df[key].str.contains("|".join(normalized_values), case=False, na=False)]
                elif isinstance(value, str):  # Фильтрация по конкретному значению (ищем вхождение)
                    normalized_value = value.strip().lower()
                    df = df[df[key].str.contains(normalized_value, case=False, na=False)]

                # Логируем результат фильтрации
                logger.debug(f"📌 Фильтр `{key}` → {value}: осталось {len(df)} записей")

        logger.info(f"✅ Итоговое количество записей после фильтрации: {len(df)}")
        return df

    except Exception as e:
        logger.error(f"❌ Ошибка при фильтрации email-таблицы: {e}", exc_info=True)
        return pd.DataFrame()


def generate_excel_from_df(df: pd.DataFrame, company_id: int, campaign_id: int) -> str:
    """
    Генерирует Excel-файл с отфильтрованными email-лидами.

    :param df: DataFrame с отфильтрованными данными.
    :param company_id: ID компании.
    :param campaign_id: ID кампании.
    :return: Путь к сгенерированному файлу.
    """
    try:
        # ✅ Создаем директорию, если её нет
        output_dir = "filtered_results"
        os.makedirs(output_dir, exist_ok=True)

        # ✅ Определяем путь к файлу
        file_path = os.path.join(output_dir, f"filtered_emails_{company_id}_{campaign_id}.xlsx")

        # ✅ Сохраняем DataFrame в Excel
        df.to_excel(file_path, index=False)

        logger.info(f"📂 Файл с фильтрованными email-лидами сохранён: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"❌ Ошибка при генерации Excel-файла: {e}", exc_info=True)
        return ""


def generate_segment_table_name(company_id: int) -> str:
    """
    Генерирует имя таблицы сегментации email-лидов на основе ID компании,
    исключая знак "-" для корректности SQL-запросов.

    :param company_id: ID компании (может быть отрицательным).
    :return: Корректное название таблицы в формате segmentation_email_<company_id>.
    """
    if company_id is None:
        logger.error("❌ Ошибка: передан company_id=None при генерации имени таблицы.")
        return None

    sanitized_company_id = abs(company_id)  # Убираем знак "-" (если есть)
    return f"segmentation_email_{sanitized_company_id}"