from sqlalchemy.orm import Session
from db.db_campaign import get_campaigns_by_company_id
from logger import logger
from db.db import SessionLocal
from db.db_company import get_company_by_chat_id
from utils.google_doc import create_excel_table
from aiogram.types import Message, FSInputFile

async def handle_view_campaigns(message: Message, state):
    """
    Обработчик для просмотра рекламных кампаний.
    """
    chat_id = str(message.chat.id)
    db: Session = SessionLocal()

    try:
        # Получаем компанию по chat_id
        company = get_company_by_chat_id(db, chat_id)
        if not company:
            await message.reply("Компания не найдена. Убедитесь, что вы зарегистрировали свою компанию.")
            return

        # Извлекаем рекламные кампании
        campaigns = get_campaigns_by_company_id(db, company.company_id)

        if not campaigns:
            await message.reply("У вас нет активных рекламных кампаний.")
            return

        # Формируем данные для таблицы Excel
        data = [["ID", "Название кампании", "Статус", "Дата создания", "Дата завершения"]]  # Заголовки таблицы
        data += [
            [
                campaign.campaign_id,
                campaign.campaign_name,
                campaign.status,
                campaign.created_at.strftime("%Y-%m-%d"),
                campaign.end_date.strftime("%Y-%m-%d") if campaign.end_date else "Не указана",
            ]
            for campaign in campaigns
        ]

        # Логируем сформированные данные для отладки
        logger.debug(f"Сформированные данные для Excel: {data}")

        # Создаем Excel-документ
        file_path = create_excel_table(data, file_name=f"campaigns_{company.name}.xlsx")

        # Отправляем Excel-файл пользователю
        excel_file = FSInputFile(file_path)
        await message.reply_document(document=excel_file, caption="Вот таблица с вашими кампаниями.")
    except Exception as e:
        logger.error(f"Ошибка при обработке просмотра кампаний: {e}", exc_info=True)
        await message.reply("Произошла ошибка при обработке вашего запроса.")
    finally:
        db.close()