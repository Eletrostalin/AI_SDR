from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import OpenAI


class LangChainHelper:
    def __init__(self, api_key):
        """
        Инициализация помощника LangChain с API ключом для доступа к LLM.
        """
        self.llm = OpenAI(api_key=api_key)

    def build_classification_chain(self):
        """
        Создает цепочку для классификации запросов, чтобы определить тип действия и сущность.
        Возвращает LLMChain для обработки запроса.
        """
        prompt = """
        Вы являетесь ассистентом, который классифицирует запросы пользователей по типу действия и сущности.
        Определите действие (создание, просмотр, редактирование, удаление) и сущность (кампания, шаблон, лид и др.).

        Пример запроса: "{user_query}"

        Ответ в формате JSON:
        {{
          "action_type": "тип действия",
          "entity_type": "тип сущности",
          "params": {{}}
        }}
        """
        prompt_template = PromptTemplate(input_variables=["user_query"], template=prompt)
        return LLMChain(llm=self.llm, prompt=prompt_template)

    async def classify_request(self, user_query):
        """
        Принимает текст запроса пользователя и возвращает классифицированный ответ
        с типом действия, сущности и параметрами (в формате JSON).
        """
        chain = self.build_classification_chain()
        response = chain.run(user_query=user_query)

        # Пример JSON-ответа после классификации
        # response = {"action_type": "create", "entity_type": "campaign", "params": {}}
        return response

