import requests
from bs4 import BeautifulSoup
import pdfplumber
from docx import Document
import mimetypes
from aiogram.types import File

# Извлечение текста из ссылки
def extract_text_from_url(url: str) -> str:
    """
    Извлекает текст с веб-страницы по URL.
    """
    response = requests.get(url)
    response.raise_for_status()  # Проверка на успешность запроса
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()

# Извлечение текста из документа
def extract_text_from_document(file_path: str, file_name: str) -> str:
    """
    Извлекает текст из документа. Поддерживаются форматы .pdf, .docx, .txt.
    """
    text = ""
    if file_name.endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif file_name.endswith(".docx"):
        text = extract_text_from_docx(file_path)
    elif file_name.endswith(".txt"):
        text = extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Формат файла {file_name} не поддерживается.")
    return text

def extract_text_from_pdf(file_path: str) -> str:
    """
    Извлекает текст из PDF-документа с использованием pdfplumber.
    """
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    except Exception as e:
        raise ValueError(f"Ошибка при обработке PDF: {e}")
    return text.strip()

def extract_text_from_docx(file_path: str) -> str:
    """
    Извлекает текст из .docx документа.
    """
    try:
        doc = Document(file_path)
        return " ".join([p.text for p in doc.paragraphs]).strip()
    except Exception as e:
        raise ValueError(f"Ошибка при обработке DOCX: {e}")

def extract_text_from_txt(file_path: str) -> str:
    """
    Извлекает текст из .txt файла.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise ValueError(f"Ошибка при обработке TXT: {e}")

# Определение типа сообщения
async def process_message(message, bot):
    """
    Определяет тип сообщения: текст, файл или ссылка.
    """
    if message.text:
        if "http" in message.text:  # Если это ссылка
            return {"type": "link", "content": message.text}
        else:
            return {"type": "text", "content": message.text}
    elif message.document:
        mime_type, _ = mimetypes.guess_type(message.document.file_name)

        # Получаем объект File
        file: File = await bot.get_file(message.document.file_id)

        # Указываем путь для временного сохранения файла
        file_path = f"/tmp/{message.document.file_name}"

        # Скачиваем файл в указанный путь
        await bot.download(file, destination=file_path)

        return {
            "type": "file",
            "mime_type": mime_type,
            "file_path": file_path,
            "file_name": message.document.file_name,
        }
    else:
        return {"type": "unknown", "content": None}