from aiogram.fsm.state import StatesGroup, State

class BaseState(StatesGroup):
    default = State()


class OnboardingState(StatesGroup):
    """
    Состояния для процесса онбординга.
    """
    waiting_for_company_name = State()
    showing_collected_data = State()
    waiting_for_missing_data = State()
    confirmation = State()


class AddCompanyState(StatesGroup):
    waiting_for_information = State()
    waiting_for_confirmation = State()
    waiting_for_company_name = State()

class AddCampaignState(StatesGroup):
    waiting_for_campaign_name = State()  # Ожидание имени кампании
    waiting_for_campaign_data = State()  # Ожидание основных данных кампании (даты и параметры)
    waiting_for_start_date = State()     # Ожидание даты начала
    waiting_for_end_date = State()       # Ожидание даты окончания
    waiting_for_missing_data = State()
    waiting_for_filters = State() # Ожидание уточнения недостающих данных
    waiting_for_confirmation = State()  # Ожидание подтверждения от пользователя

class AddContentPlanState(StatesGroup):
    waiting_for_description = State()
    waiting_for_wave_count = State()
    waiting_for_wave_details = State()
    waiting_for_confirmation = State()

class AddEmailSegmentationState(StatesGroup):
    """
    Состояния для добавления таблицы сегментации по email.
    """
    waiting_for_file_upload = State()  # Ожидание загрузки файла
    waiting_for_mapping_confirmation = State()  # Подтверждение сопоставления колонок

class EditCompanyState(StatesGroup):
    waiting_for_updated_info = State()
    waiting_for_confirmation = State()

class SegmentationState(StatesGroup):
    waiting_for_filters = State()
    waiting_for_confirmation = State()


class DeleteCampaignState(StatesGroup):
    waiting_for_campaign_selection = State()
    waiting_for_campaign_confirmation = State()

# Состояния для работы с шаблонами
class TemplateStates(StatesGroup):
    """
    Состояния для создания и подтверждения шаблонов.
    """
    waiting_for_description = State()  # Ожидание ввода пожеланий
    waiting_for_confirmation = State()  # Ожидание подтверждения шаблона
    refining_template = State()  # Уточнение пожеланий для доработки шаблона
    waiting_for_edit_input = State()
    waiting_for_confirmation = State() # Ожидание пользовательского ввода для редактирования
