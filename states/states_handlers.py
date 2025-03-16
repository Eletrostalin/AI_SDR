from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import CallbackQuery

# Импорт обработчиков для различных состояний
from handlers.company_handlers.company_handlers import (
    process_company_information,
    handle_add_company,
    confirm_company_information,
    process_edit_company_information,
    confirm_edit_company_information
)

from handlers.campaign_handlers.campaign_handlers import (
    process_campaign_name,
    process_filters
)
from handlers.content_plan_handlers.content_plan_handlers import process_audience_style, \
    process_send_date #process_restricted_topics, process_wave_name
from handlers.email_table_handler import handle_file_upload, handle_email_choice_callback, handle_campaign_decision, \
    handle_first_question_decision, handle_second_question_decision
from handlers.onboarding_handler import (
    handle_brief_upload, confirm_brief, handle_missing_fields_response)
from handlers.template_handlers.template_handler import handle_user_input, confirm_template
from states.states import (
    OnboardingState,
    EditCompanyState,
    AddCampaignState,
    AddContentPlanState,
    AddCompanyState, TemplateStates, EmailProcessingDecisionState, EmailUploadState
)

from logger import logger


async def process_email_connections(message, state):
    pass


async def handle_onboarding_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния онбординга.
    """
    if current_state == OnboardingState.waiting_for_brief.state:
        await handle_brief_upload(message, state)

    elif current_state == OnboardingState.missing_fields.state:
        await handle_missing_fields_response(message, state)

    elif current_state == OnboardingState.confirmation.state:
        await confirm_brief(message, state)

    else:
        # Если состояние не распознано
        await message.answer("❌ Неизвестное состояние. Пожалуйста, начните заново.")
        await state.clear()


async def handle_email_upload_states(event: Message | CallbackQuery, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния, связанные с загрузкой email-таблицы.
    """
    logger.debug(f"🔄 Обрабатываем состояние загрузки файла: {current_state} | Тип события: {type(event)}")

    if isinstance(event, Message):  # Если это обычное сообщение
        if current_state == EmailUploadState.waiting_for_file_upload:
            await handle_file_upload(event, state)

        elif current_state == EmailUploadState.duplicate_email_check:
            await handle_email_choice_callback(event, state)  # Обрабатываем выбор пользователя по email

        else:
            logger.warning(f"⚠️ Неизвестное состояние: {current_state}. Сообщение будет проигнорировано.")
            await event.reply("Произошла ошибка. Непонятное состояние. Попробуйте ещё раз или свяжитесь с поддержкой.")

    elif isinstance(event, CallbackQuery):  # Если это callback-запрос
        logger.warning(f"⚠️ Callback получен в состоянии загрузки email, но не обработан: {current_state}")
        await event.answer("Произошла ошибка. Попробуйте ещё раз.", show_alert=True)


async def handle_email_processing_decisions(event: CallbackQuery, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния, связанные с выбором дальнейших действий (добавление еще файлов или запуск кампании).
    """
    logger.debug(f"🔄 Обрабатываем состояние выбора: {current_state} | Тип события: {type(event)}")

    if current_state == EmailProcessingDecisionState.waiting_for_more_files_decision:
        await handle_first_question_decision(event, state)  # Обрабатываем выбор загрузки файлов

    elif current_state == EmailProcessingDecisionState.waiting_for_campaign_decision:
        await handle_second_question_decision(event, state)  # Обрабатываем выбор старта кампании

    else:
        logger.warning(f"⚠️ Неизвестное состояние для callback: {current_state}.")
        await event.answer("Произошла ошибка. Попробуйте ещё раз.", show_alert=True)


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
    elif current_state == AddCampaignState.waiting_for_filters.state:
        await process_filters(message, state)
    else:
        # Обработка неизвестного состояния
        await message.reply("Неизвестное состояние. Начните процесс заново.")
        await state.clear()


async def handle_add_content_plan_states(message: Message, state: FSMContext, current_state: str):
    """
    Обрабатывает состояния добавления контентного плана.
    """
    # if current_state == AddContentPlanState.waiting_for_restricted_topics.state:
    #     await process_restricted_topics(message, state)
    if current_state == AddContentPlanState.waiting_for_audience_style.state:
        await process_audience_style(message, state)
    # elif current_state == AddContentPlanState.waiting_for_wave_name.state:  # Новый шаг
    #     await process_wave_name(message, state)
    elif current_state == AddContentPlanState.waiting_for_send_date.state:
        await process_send_date(message, state)


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