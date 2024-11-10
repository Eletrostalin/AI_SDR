from langchain_helper import LangChainHelper
from bot.chains import campaigns, templates, email_tables, responses


class ChainDispatcher:
    def __init__(self):
        # Инициализируем LangChainHelper с ключом API для доступа к LLM
        self.langchain_helper = LangChainHelper(api_key="YOUR_OPENAI_API_KEY")

    async def route_request(self, user_query):
        """
        Классифицирует запрос пользователя и направляет его в нужную цепочку для обработки.

        :param user_query: Текст запроса пользователя
        :return: Ответ, сформированный цепочкой, в зависимости от классификации
        """
        # Классифицируем запрос пользователя
        classification = await self.langchain_helper.classify_request(user_query)
        action_type = classification.get("action_type")
        entity_type = classification.get("entity_type")
        params = classification.get("params", {})

        # Выбираем соответствующую цепочку в зависимости от типа сущности и действия
        if entity_type == "campaign":
            return await self.handle_campaign(action_type, params)
        elif entity_type == "template":
            return await self.handle_template(action_type, params)
        elif entity_type == "email_table":
            return await self.handle_email_table(action_type, params)
        elif entity_type == "response":
            return await self.handle_response(action_type, params)
        else:
            return "Запрос не распознан. Пожалуйста, уточните ваш запрос."

    async def handle_campaign(self, action_type, params):
        """
        Обработка действий с кампаниями.
        """
        if action_type == "create":
            return await campaigns.create_campaign(params)
        elif action_type == "view":
            return await campaigns.view_campaigns(params)
        elif action_type == "edit":
            return await campaigns.edit_campaign(params)
        elif action_type == "delete":
            return await campaigns.delete_campaign(params)
        else:
            return "Неизвестное действие для кампании."

    async def handle_template(self, action_type, params):
        """
        Обработка действий с шаблонами.
        """
        if action_type == "create":
            return await templates.create_template(params)
        elif action_type == "view":
            return await templates.view_templates(params)
        elif action_type == "edit":
            return await templates.edit_template(params)
        elif action_type == "delete":
            return await templates.delete_template(params)
        else:
            return "Неизвестное действие для шаблона."

    async def handle_email_table(self, action_type, params):
        """
        Обработка действий с таблицами лидов.
        """
        if action_type == "create":
            return await email_tables.create_email_table(params)
        elif action_type == "view":
            return await email_tables.view_email_tables(params)
        elif action_type == "edit":
            return await email_tables.edit_email_table(params)
        elif action_type == "delete":
            return await email_tables.delete_email_table(params)
        else:
            return "Неизвестное действие для таблицы лидов."

    async def handle_response(self, action_type, params):
        """
        Обработка действий с входящими сообщениями.
        """
        if action_type == "create":
            return await responses.create_response(params)
        elif action_type == "view":
            return await responses.view_responses(params)
        elif action_type == "edit":
            return await responses.edit_response(params)
        elif action_type == "delete":
            return await responses.delete_response(params)
        else:
            return "Неизвестное действие для входящих сообщений."