from aiogram.fsm.state import StatesGroup, State

class BaseState(StatesGroup):
    default = State()


class AddCompanyState(StatesGroup):
    waiting_for_information = State()
    waiting_for_confirmation = State()
    waiting_for_company_name = State()


class AddCampaignState(StatesGroup):
    waiting_for_campaign_information = State()
    waiting_for_campaign_name = State()
    waiting_for_confirmation = State()


class EditCompanyState(StatesGroup):
    waiting_for_updated_info = State()


class DeleteCampaignState(StatesGroup):
    waiting_for_campaign_selection = State()
    waiting_for_campaign_confirmation = State()