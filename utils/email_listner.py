import asyncio
import email
import logging
from email.header import decode_header
from imapclient import IMAPClient
from sqlalchemy.orm import sessionmaker
import httpx

from config import IMAP_PORT, EMAIL_ACCOUNT, IMAP_SERVER, EMAIL_PASSWORD
from db.db import engine  # Импортируем модель Wave из вашей базы данных  # Функция для отправки уведомлений

from db.models import Waves

# 🔹 ID чата для уведомлений
GENERAL_CHAT_ID = -1001234567890  # Замените на ID вашего Telegram-чата

# Настраиваем логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем сессию SQLAlchemy
SessionLocal = sessionmaker(bind=engine)

async def check_new_emails():
    """
    Функция подключается к IMAP-серверу, проверяет новые входящие письма и обрабатывает их.
    """
    try:
        with IMAPClient(IMAP_SERVER, port=IMAP_PORT) as client:
            client.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            client.select_folder("INBOX")  # Выбираем папку "Входящие"

            while True:
                logger.info("🔍 Проверяем новые письма...")
                messages = client.search(["UNSEEN"])  # Ищем непрочитанные письма

                if messages:
                    logger.info(f"📩 Найдено {len(messages)} новых писем")

                    for msgid in messages:
                        raw_message = client.fetch(msgid, ["RFC822"])[msgid][b"RFC822"]
                        email_message = email.message_from_bytes(raw_message)

                        subject, encoding = decode_header(email_message["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8")

                        logger.info(f"📧 Входящее письмо с темой: {subject}")

                        # Проверяем, есть ли такая тема в таблице wave
                        with SessionLocal() as db:
                            wave = db.query(Waves).filter(Waves.subject == subject).first()

                            if wave:
                                logger.info(f"✅ Тема письма совпадает с волной ID {wave.wave_id}")
                                await send_telegram_message(
                                    GENERAL_CHAT_ID,
                                    f"📩 Новое письмо по кампании **{wave.subject}**!"
                                )

                        # Помечаем письмо как прочитанное
                        client.add_flags(msgid, ["\\Seen"])

                # ⏳ Ожидаем 60 секунд перед следующей проверкой
                await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке почты: {e}", exc_info=True)


async def send_telegram_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.post(TELEGRAM_API_URL, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


async def main():
    """
    Запуск основного цикла проверки почты.
    """
    while True:
        await check_new_emails()
        await asyncio.sleep(10)  # Повторяем цикл каждые 10 секунд


if __name__ == "__main__":
    asyncio.run(main())