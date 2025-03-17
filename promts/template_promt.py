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

def generate_email_template_prompt(company_details: dict) -> str:
    """
    Формирует промт для генерации email-шаблона с учетом запрета на определенные слова.

    :param company_details: Словарь с деталями о компании и пользовательским запросом.
    :return: Текстовый промт.
    """
    forbidden_words = [
        "Нажми сюда!", "Получили миллион за минуту!", "бесплатно", "прибыль", "профит", "100%", "0%",
        "получи бесплатно", "Финансовый успех", "Деньги", "Кредит", "Жми", "Кликни", "Купи", "Скачай",
        "Хотите получать 1000 долларов в день?", "Скачай бесплатно!", "Подарок!",
        "Дарим презент, если откроете письмо!", "Похудение", "Лекарства", "Медицинская страховка",
        "Скидка", "Бесплатно", "Выиграйте", "Акция", "Легко заработать",
        "Не требует проверки кредитной истории", "Гарантированно", "Не потеряйте свой шанс",
        "Взрослые", "Секс", "Выиграли лотерею", "Наследство от незнакомца", "Помощь в получении кредита"
    ]

    return (
        f"Ты – AI-ассистент, создающий email-шаблоны для компаний. Учитывай следующую информацию:\n\n"
        f"- Название компании: {company_details.get('company_name')}\n"
        f"- Миссия компании: {company_details.get('company_mission')}\n"
        f"- Ценности компании: {company_details.get('company_values')}\n"
        f"- Отрасль: {company_details.get('business_sector')}\n"
        f"- Адреса и время работы: {company_details.get('office_addresses_and_hours')}\n"
        f"- Ссылки на ресурсы: {company_details.get('resource_links')}\n"
        f"- Целевая аудитория и география: {company_details.get('target_audience_b2b_b2c_niche_geography')}\n"
        f"- УТП: {company_details.get('unique_selling_proposition')}\n"
        f"- Боли клиентов: {company_details.get('customer_pain_points')}\n"
        f"- Отличия от конкурентов: {company_details.get('competitor_differences')}\n"
        f"- Продукты и услуги: {company_details.get('promoted_products_and_services')}\n"
        f"- Доставка и покрытие: {company_details.get('delivery_availability_geographical_coverage')}\n"
        f"- FAQ: {company_details.get('frequently_asked_questions_with_answers')}\n"
        f"- Типичные возражения клиентов и ответы: {company_details.get('common_customer_objections_and_responses')}\n"
        f"- Успешные кейсы: {company_details.get('successful_case_studies')}\n"
        f"- Дополнительная информация: {company_details.get('additional_information')}\n\n"
        f"Контент-план:\n"
        f"- {company_details.get('content_plan_description')}\n\n"
        f"Пользователь просит создать шаблон с учетом следующих пожеланий:\n"
        f"\"{company_details.get('user_request')}\"\n\n"
        f"**Твоя задача:**\n"
        f"- Сформировать качественный email-шаблон без темы письма.\n"
        f"- **Строго запрещено** использовать следующие слова или их вариации:\n"
        f"  {', '.join(forbidden_words)}.\n"
        f"- Шаблон должен выглядеть естественно.\n"
    )