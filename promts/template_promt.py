from langchain.prompts import ChatPromptTemplate

# 1. Промт для запроса пожеланий у пользователя
invite_prompt = ChatPromptTemplate.from_template("""
Ты AI-ассистент. Попроси пользователя тактично ввести пожелания для генерации шаблонов письма. 
Формулируй просьбу по-разному каждый раз, чтобы пользователь не замечал однотипности.
Отвечай только одной строкой текста без дополнительных структур JSON или метаданных.
""")

# 2. Промт для анализа пользовательского ввода (если снова понадобится)
context_analysis_prompt = ChatPromptTemplate.from_template("""
Мы ожидаем текст с пожеланиями для шаблона письма. Текст: {input}

Если текст соответствует ожиданиям, ответь "valid".
Если текст не соответствует, ответь "invalid" и кратко объясни, почему.
""")

# 3. Промт для генерации письма с учётом компании и контентного плана
template_generation_prompt = ChatPromptTemplate.from_template("""
Сгенерируй текст письма для компании "{company_name}" (сфера: {industry}).

Контентный план: {content_plan}
Тема письма: {subject}

Пожелания пользователя:
{user_request}

Ответ должен быть строго на русском
""")

template_edit_prompt = ChatPromptTemplate.from_template("""
Ты – профессиональный редактор email-рассылок. Твоя задача – внести изменения в шаблон письма на основе комментариев пользователя.

**Исходный текст письма**:
{current_template}

✏**Комментарии пользователя**:
{comments}

**Твоя задача**:
- Сохрани стиль и суть письма.
- Учитывай комментарии пользователя.
- Не добавляй лишнюю информацию.
- Отвечай **только новым текстом письма**, без пояснений.

📝 **Новый текст письма**:
""")

def generate_email_prompt(company_details: dict) -> str:
    """
    Формирует текстовый промпт для генерации email-шаблона на основе данных компании, контент-плана и пожеланий пользователя.

    :param company_details: Словарь с данными о компании, контент-плане и пожеланиями пользователя.
    :return: Строка с промптом для модели.
    """
    return f"""
    Ты – AI-ассистент, создающий email-шаблоны для компаний. Учитывай следующую информацию:

    - Название компании: {company_details.get("company_name")}
    - Миссия компании: {company_details.get("company_mission")}
    - Ценности компании: {company_details.get("company_values")}
    - Отрасль: {company_details.get("business_sector")}
    - Адреса и время работы: {company_details.get("office_addresses_and_hours")}
    - Ссылки на ресурсы: {company_details.get("resource_links")}
    - Целевая аудитория и география: {company_details.get("target_audience_b2b_b2c_niche_geography")}
    - УТП: {company_details.get("unique_selling_proposition")}
    - Боли клиентов: {company_details.get("customer_pain_points")}
    - Отличия от конкурентов: {company_details.get("competitor_differences")}
    - Продукты и услуги: {company_details.get("promoted_products_and_services")}
    - Доставка и покрытие: {company_details.get("delivery_availability_geographical_coverage")}
    - FAQ: {company_details.get("frequently_asked_questions_with_answers")}
    - Типичные возражения клиентов и ответы: {company_details.get("common_customer_objections_and_responses")}
    - Успешные кейсы: {company_details.get("successful_case_studies")}
    - Дополнительная информация: {company_details.get("additional_information")}

    Контент-план:
    - {company_details.get("content_plan_description")}

    Пользователь просит создать шаблон с учетом следующих пожеланий:
    "{company_details.get("user_request")}"

    Сформируй качественный email-шаблон. Subject не нужен, только шаблон письма.
    """