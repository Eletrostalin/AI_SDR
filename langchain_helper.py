from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.chat_models import ChatOpenAI


class LangChainHelper:
    def __init__(self, api_key: str):
        """
        Инициализация LangChainHelper с API-ключом для доступа к OpenAI.
        """
        self.llm = ChatOpenAI(
            openai_api_key=api_key,
            model="gpt-4",  # Можно использовать "gpt-3.5-turbo" для экономии
            temperature=0.0  # Устанавливаем нулевую температуру для более детерминированных ответов
        )

    def build_classification_chain(self, prompt_template: str):
        """
        Создаёт цепочку для обработки запросов с использованием переданного шаблона.
        :param prompt_template: Шаблон текста для генерации ответа.
        :return: Экземпляр LLMChain.
        """
        prompt = PromptTemplate(
            input_variables=["user_query"],
            template=prompt_template
        )
        return LLMChain(llm=self.llm, prompt=prompt)

    async def classify_request(self, user_query: str) -> dict:
        """
        Обрабатывает пользовательский запрос, используя LLMChain.
        :param user_query: Текст запроса.
        :return: Результат обработки запроса в виде JSON.
        """
        # Определяем шаблон для классификации
        prompt_template = """
        Извлеки данные о компании из следующей информации:
        {user_query}

        Верни их в формате JSON:
        {{
            "company_name": "Название компании",
            "industry": "Сфера деятельности",
            "location": "Местоположение",
            "description": "Описание"
        }}
        """

        try:
            # Создаём цепочку
            chain = self.build_classification_chain(prompt_template)

            # Выполняем обработку текста
            response = chain.run(user_query=user_query)

            # Преобразуем ответ в JSON
            import json
            result = json.loads(response)
            return result
        except Exception as e:
            # Возвращаем ошибку при сбое
            return {"error": str(e)}