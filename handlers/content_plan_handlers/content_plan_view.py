from aiogram.fsm.context import FSMContext
from sqlalchemy.orm import Session
from db.db_campaign import get_campaigns_by_company_id
from db.db_content_plan import get_content_plans_by_campaign_id
from db.db_company import get_company_by_chat_id
from logger import logger
from utils.google_doc import create_excel_table
from aiogram.types import Message, FSInputFile
from db.db import SessionLocal

async def handle_view_content_plans(message: Message, state: FSMContext):

    """
    Обработчик для просмотра контентных планов и генерации Excel-файла.
    """
    chat_id = str(message.chat.id)
    db: Session = SessionLocal()

    try:
        # Получаем компанию по chat_id
        company = get_company_by_chat_id(db, chat_id)
        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return

        # Извлекаем рекламные кампании компании
        campaigns = get_campaigns_by_company_id(db, company.company_id)
        if not campaigns:
            await message.reply("У вас нет активных рекламных кампаний.")
            return

        # Формируем данные для Excel
        data = [["ID кампании", "Название кампании", "ID контентного плана", "Описание", "Количество волн", "Дата создания"]]

        for campaign in campaigns:
            # Получаем контентные планы для текущей кампании
            content_plans = get_content_plans_by_campaign_id(db, campaign.campaign_id)

            if not content_plans:
                data.append([
                    campaign.campaign_id,
                    campaign.campaign_name,
                    "Нет данных",
                    "Нет данных",
                    "Нет данных",
                    "Нет данных"
                ])
                continue

            for content_plan in content_plans:
                data.append([
                    campaign.campaign_id,
                    campaign.campaign_name,
                    content_plan.content_plan_id,
                    content_plan.description or "Описание отсутствует",
                    content_plan.wave_count,
                    content_plan.created_at.strftime("%Y-%m-%d") if content_plan.created_at else "Не указано"
                ])

        # Логируем сформированные данные для отладки
        logger.debug(f"Сформированные данные для Excel: {data}")

        # Создаем Excel-документ
        file_name = f"content_plans_{company.name}.xlsx"
        file_path = create_excel_table(data, file_name=file_name)

        # Отправляем Excel-файл пользователю
        excel_file = FSInputFile(file_path)
        await message.reply_document(document=excel_file, caption="Вот таблица с вашими контентными планами.")

    except Exception as e:
        logger.error(f"Ошибка при обработке просмотра контентных планов: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса.")
    finally:
        db.close()