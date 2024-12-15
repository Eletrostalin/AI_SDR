from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from db.db import SessionLocal
from db.models import CompanyInfo
from states.states import OnboardingState
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(OnboardingState.waiting_for_company_name)
async def handle_company_name(message: Message, state: FSMContext):
    """
    Обработка названия компании.
    """
    await state.update_data(company_name=message.text)
    await state.set_state(OnboardingState.waiting_for_industry)
    await message.answer("Отлично! Теперь укажите сферу деятельности вашей компании.")


@router.message(OnboardingState.waiting_for_industry)
async def handle_industry(message: Message, state: FSMContext):
    """
    Обработка сферы деятельности.
    """
    await state.update_data(industry=message.text)
    await state.set_state(OnboardingState.waiting_for_region)
    await message.answer("Какой регион или географию работы охватывает ваша компания?")


@router.message(OnboardingState.waiting_for_region)
async def handle_region(message: Message, state: FSMContext):
    """
    Обработка региона.
    """
    await state.update_data(region=message.text)
    await state.set_state(OnboardingState.waiting_for_contact_email)
    await message.answer("Укажите основной email для связи.")


@router.message(OnboardingState.waiting_for_contact_email)
async def handle_contact_email(message: Message, state: FSMContext):
    """
    Обработка email.
    """
    await state.update_data(contact_email=message.text)
    await state.set_state(OnboardingState.waiting_for_contact_phone)
    await message.answer("Укажите контактный номер телефона (можно пропустить, отправив 'Пропустить').")


@router.message(OnboardingState.waiting_for_contact_phone)
async def handle_contact_phone(message: Message, state: FSMContext):
    """
    Обработка телефона.
    """
    if message.text.lower() != "пропустить":
        await state.update_data(contact_phone=message.text)
    await state.set_state(OnboardingState.waiting_for_additional_details)
    await message.answer("Есть ли дополнительные данные, которые вы хотите добавить? Напишите их или отправьте 'Пропустить'.")


@router.message(OnboardingState.waiting_for_additional_details)
async def handle_additional_details(message: Message, state: FSMContext):
    """
    Обработка дополнительных данных.
    """
    if message.text.lower() != "пропустить":
        await state.update_data(additional_info=message.text)

    # Переход к подтверждению
    data = await state.get_data()
    await state.set_state(OnboardingState.confirmation)
    await message.answer(
        "Проверьте данные:\n"
        f"📌 Название компании: {data.get('company_name')}\n"
        f"📌 Сфера деятельности: {data.get('industry')}\n"
        f"📌 Регион: {data.get('region')}\n"
        f"📌 Email: {data.get('contact_email')}\n"
        f"📌 Телефон: {data.get('contact_phone', 'не указан')}\n"
        f"📌 Дополнительно: {data.get('additional_info', 'не указано')}\n\n"
        "Подтвердите, отправив 'Да'. Если хотите начать заново, отправьте 'Нет'."
    )


@router.message(OnboardingState.confirmation)
async def handle_confirmation(message: Message, state: FSMContext):
    """
    Подтверждение данных компании.
    """
    if message.text.lower() == "да":
        data = await state.get_data()
        company_id = data.get("company_id")

        if not company_id:
            await message.answer("Ошибка: Не удалось получить данные о компании. Повторите онбординг.")
            await state.set_state(OnboardingState.waiting_for_company_name)
            return

        db: Session = SessionLocal()
        try:
            # Сохраняем данные компании в таблицу CompanyInfo
            company_info = CompanyInfo(
                company_id=company_id,
                company_name=data.get("company_name"),
                industry=data.get("industry"),
                region=data.get("region"),
                contact_email=data.get("contact_email"),
                contact_phone=data.get("contact_phone"),
                additional_info=data.get("additional_info"),
            )
            db.add(company_info)
            db.commit()

            await message.answer(
                "🎉 Данные компании успешно сохранены! Теперь вы можете начать работу с ботом.\n"
                "Напишите 'Помощь', чтобы узнать, что я могу делать."
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения данных компании: {e}", exc_info=True)
            await message.answer("Произошла ошибка при сохранении данных. Попробуйте снова.")
        finally:
            db.close()

        await state.clear()
    else:
        await state.set_state(OnboardingState.waiting_for_company_name)
        await message.answer("Опрос начат заново. Введите название вашей компании.")