from aiogram.fsm.context import FSMContext
from aiogram.types import Message

# Импорт обработчиков для различных состояний
from handlers.company_handlers.company_handlers import (
    process_company_information,
    handle_add_company,
    confirm_company_information,
    process_edit_company_information,
    confirm_edit_company_information
)
from handlers.content_plan_handlers.content_plan_handlers import (
    process_content_plan_description,
    process_wave_count,
    process_wave_details,
    confirm_content_plan
)
from handlers.campaign_handlers.campaign_handlers import (
    process_campaign_name,
    process_start_date,
    process_end_date,
    confirm_campaign_creation,
    process_campaign_data,
    process_filters
)
from handlers.email_table_handler import handle_file_upload, handle_email_choice_callback
from handlers.onboarding_handler import (
    handle_brief_upload, process_brief, confirm_brief, handle_missing_fields_response)
from handlers.template_handlers.template_handler import handle_user_input, confirm_template
from states.states import (
    OnboardingState,
    AddEmailSegmentationState,
    EditCompanyState,
    AddCampaignState,
    AddContentPlanState,
    AddCompanyState, TemplateStates
)

from logger import logger


async def handle_onboarding_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния онбординга.
    """
    if current_state == OnboardingState.waiting_for_brief.state:
        await handle_brief_upload(message, state)

    elif current_state == OnboardingState.processing_brief.state:
        await process_brief(message, state)

    elif current_state == OnboardingState.missing_fields.state:
        await handle_missing_fields_response(message, state)  # Добавили обработчик пропущенных полей

    elif current_state == OnboardingState.confirmation.state:
        await confirm_brief(message, state)

    else:
        # Если состояние не распознано
        await message.answer("Неизвестное состояние. Пожалуйста, начните заново.")
        await state.clear()


async def handle_add_email_segmentation_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления email-таблицы.
    """
    if current_state == AddEmailSegmentationState.waiting_for_file_upload.state:
        await handle_file_upload(message, state)

    elif current_state == AddEmailSegmentationState.duplicate_email_check.state:
        await handle_email_choice_callback(message, state)  # Обрабатываем выбор пользователя по email

    else:
        logger.warning(f"Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")
        await message.reply("Произошла ошибка. Непонятное состояние. Попробуйте ещё раз или свяжитесь с поддержкой.")

# Обработка состояний редактирования компании
async def handle_edit_company_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния редактирования компании.
    """
    if current_state == AddCompanyState.waiting_for_information.state:
        await process_company_information(message, state, bot=message.bot)
    elif current_state == AddCompanyState.waiting_for_company_name.state:
        await handle_add_company(message, state)
    elif current_state == AddCompanyState.waiting_for_confirmation.state:
        await confirm_company_information(message, state)
    elif current_state == EditCompanyState.waiting_for_updated_info.state:
        await process_edit_company_information(message, state)
    elif current_state == EditCompanyState.waiting_for_confirmation.state:
        await confirm_edit_company_information(message, state)
    else:
        # Если состояние не распознано
        await message.answer("Неизвестное состояние. Пожалуйста, начните заново.")
        await state.clear()

# Обработка состояний добавления кампании
async def handle_add_campaign_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления кампании.
    """
    if current_state == AddCampaignState.waiting_for_campaign_name.state:
        await process_campaign_name(message, state)
    elif current_state == AddCampaignState.waiting_for_campaign_data.state:
        await process_campaign_data(message, state)
    elif current_state == AddCampaignState.waiting_for_start_date.state:
        await process_start_date(message, state)
    elif current_state == AddCampaignState.waiting_for_end_date.state:
        await process_end_date(message, state)
    elif current_state == AddCampaignState.waiting_for_filters.state:
        await process_filters(message, state)
    elif current_state == AddCampaignState.waiting_for_confirmation.state:
        await confirm_campaign_creation(message, state)
    else:
        # Обработка неизвестного состояния
        await message.reply("Неизвестное состояние. Начните процесс заново.")
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
        await handle_user_input(message, state)
    elif current_state == TemplateStates.waiting_for_confirmation.state:
        await confirm_template(message, state)
    # elif current_state == TemplateStates.refining_template.state:
    #     await refine_template(message, state)