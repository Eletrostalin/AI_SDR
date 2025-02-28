from aiogram.fsm.state import StatesGroup, State

class BaseState(StatesGroup):
    default = State()


class OnboardingState(StatesGroup):
    waiting_for_brief = State()  # Ожидание загрузки брифа
    processing_brief = State()  # Обработка загруженного брифа
    confirmation = State()  # Подтверждение успешной загрузки
    missing_fields = State()


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
    duplicate_email_check = State()  # Проверка записей с несколькими email
    waiting_for_more_files_decision = State()  # Ожидание решения пользователя о загрузке еще одного файла

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
