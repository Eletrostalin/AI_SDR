from aiogram.fsm.state import StatesGroup, State

class BaseState(StatesGroup):
    """
    Базовое состояние, обрабатывающее запросы пользователя.
    """
    default = State()


class AddCompanyState(StatesGroup):
    waiting_for_information = State()
    waiting_for_confirmation = State()


class AddCampaignState(StatesGroup):
    waiting_for_campaign_information = State()
    waiting_for_confirmation = State()