from chat_handlers import router as chat_router
from handlers.company_handlers import router as company_router
from handlers.campaign_handlers import router as campaign_router  # Добавляем маршрутизатор кампаний
from handlers.campaign_delete_handler import handle_campaign_selection, \
    handle_campaign_deletion_confirmation  # Импортируем обработчик выбора кампании
from aiogram.filters import StateFilter  # Импорт фильтра для состояния
from utils.states import DeleteCampaignState  # Импорт состояния удаления кампании
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Инициализация асинхронного клиента

def setup_routers(dp):
    """
    Настраивает маршрутизаторы, подключая обработчики для чата с пользователями
    и для команд администратора.
    """
    dp.include_router(chat_router)
    dp.include_router(company_router)
    dp.include_router(campaign_router)

    # Регистрация обработчика для выбора кампании
    dp.message.register(
        handle_campaign_selection,
        StateFilter(DeleteCampaignState.waiting_for_campaign_selection),
    )

    # Регистрация обработчика для подтверждения удаления кампании
    dp.message.register(
        handle_campaign_deletion_confirmation,
        StateFilter(DeleteCampaignState.waiting_for_campaign_confirmation),
    )