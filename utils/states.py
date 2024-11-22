from aiogram.fsm.state import StatesGroup, State


class AddCompanyState(StatesGroup):
    waiting_for_information = State()
    waiting_for_confirmation = State()