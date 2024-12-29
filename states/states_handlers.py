from aiogram.fsm.context import FSMContext
from aiogram.types import Message

# Импорты обработчиков для контентного плана
from handlers.content_plan_handlers.content_plan_handlers import (
    process_content_plan_description,
    process_wave_count,
    process_wave_details,
    confirm_content_plan
)

# Импорты обработчиков для онбординга


# Импорты обработчиков для редактирования компании
from handlers.company_handlers.company_handlers import (
    process_edit_company_information,
    confirm_edit_company_information
)

# Импорты обработчиков для кампаний
from handlers.campaign_handlers.campaign_handlers import (
    process_campaign_name,
    confirm_campaign_creation,
    process_campaign_data,
    process_start_date,
    process_end_date,
    process_filters
)

# Импорты для работы с email таблицами
from handlers.email_table_handler import handle_file_upload, logger
from handlers.tamplate_handlers.tamplate_handler import confirm_template, generate_template, handle_subject

# Импорт состояний
from states.states import (
    OnboardingState,
    AddEmailSegmentationState,
    EditCompanyState,
    AddCampaignState,
    AddContentPlanState, TemplateStates,
)



async def handle_add_email_segmentation_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления email-таблицы.
    """
    if current_state == AddEmailSegmentationState.waiting_for_file_upload.state:
        await handle_file_upload(message, state)
   # elif current_state == AddEmailSegmentationState.waiting_for_mapping_confirmation.state:
        # await handle_mapping_confirmation(message, state)
    else:
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")
        await message.reply("Произошла ошибка. Непонятное состояние. Попробуйте ещё раз или свяжитесь с поддержкой.")

# Обработка состояний редактирования компании
async def handle_edit_company_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния редактирования компании.
    """
    if current_state == EditCompanyState.waiting_for_updated_info.state:
        await process_edit_company_information(message, state)
    elif current_state == EditCompanyState.waiting_for_confirmation.state:
        await confirm_edit_company_information(message, state)

# Обработка состояний добавления кампании
async def handle_add_campaign_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления кампании.
    """
    if current_state == AddCampaignState.waiting_for_campaign_name.state:
        # Обработка ввода названия кампании
        await process_campaign_name(message, state)
    elif current_state == AddCampaignState.waiting_for_campaign_data.state:
        # Обработка ввода данных кампании (даты и фильтров)
        await process_campaign_data(message, state)
    elif current_state == AddCampaignState.waiting_for_start_date.state:
        # Обработка ввода даты начала кампании
        await process_start_date(message, state)
    elif current_state == AddCampaignState.waiting_for_end_date.state:
        # Обработка ввода даты окончания кампании
        await process_end_date(message, state)
    elif current_state == AddCampaignState.waiting_for_filters.state:
        # Обработка ввода фильтров сегментации
        await process_filters(message, state)
    elif current_state == AddCampaignState.waiting_for_confirmation.state:
        # Обработка подтверждения данных кампании
        await confirm_campaign_creation(message, state)
    else:
        # Если состояние неизвестно
        logger.warning(f"Неизвестное состояние: {current_state}")
        await message.reply("Произошла ошибка. Попробуйте начать процесс создания кампании заново.")
        await state.clear()

async def handle_add_content_plan_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления контентного плана.
    """
    if current_state == AddContentPlanState.waiting_for_description.state:
        # Обработка ввода описания контентного плана
        await process_content_plan_description(message, state)
    elif current_state == AddContentPlanState.waiting_for_wave_count.state:
        # Обработка ввода количества волн
        await process_wave_count(message, state)
    elif current_state == AddContentPlanState.waiting_for_wave_details.state:
        # Обработка ввода данных для волн
        await process_wave_details(message, state)
    elif current_state == AddContentPlanState.waiting_for_confirmation.state:
        # Обработка подтверждения контентного плана
        await confirm_content_plan(message, state)

async def handle_template_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния создания шаблонов.
    """
    if current_state == TemplateStates.waiting_for_description.state:
        await generate_template(message, state)
    elif current_state == TemplateStates.waiting_for_subject.state:
        await handle_subject(message, state)
    elif current_state == TemplateStates.waiting_for_confirmation.state:
        await confirm_template(message, state)
