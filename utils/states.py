from aiogram.fsm.state import StatesGroup, State

class BaseState(StatesGroup):
    default = State()

class OnboardingState(StatesGroup):
    """
    Состояния для процесса онбординга.
    """
    waiting_for_company_name = State()  # Ожидание ввода названия компании
    waiting_for_industry = State()      # Ожидание ввода сферы деятельности
    waiting_for_region = State()        # Ожидание ввода региона
    waiting_for_contact_email = State() # Ожидание ввода email
    waiting_for_contact_phone = State() # Ожидание ввода контактного телефона
    waiting_for_additional_details = State()  # Ожидание ввода дополнительных данных
    confirmation = State()              # Подтверждение данных

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