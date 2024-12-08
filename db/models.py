from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, func, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String, nullable=False, unique=True)
    added_at = Column(DateTime, default=func.now(), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=True)
    name = Column(String, nullable=True)

    # Связь с таблицей companies
    company = relationship("Company", back_populates="users")

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    thread_id = Column(BigInteger, nullable=False, index=True)
    thread_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

# Таблица Company
class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False, unique=True)
    telegram_id = Column(String, nullable=False)
    creation_date = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String, default="active", nullable=False)
    name = Column(String, nullable=True)

    info = relationship("CompanyInfo", back_populates="company")
    campaigns = relationship("Campaigns", back_populates="company")
    users = relationship("User", back_populates="company")

# Таблица CompanyInfo
class CompanyInfo(Base):
    __tablename__ = "company_info"

    company_info_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    company_name = Column(String(255), nullable=False)  # Название компании
    industry = Column(String(255), nullable=False)  # Отрасль/сфера деятельности
    region = Column(String(255), nullable=True)  # Регион/география работы
    contact_email = Column(String(255), nullable=False)  # Основной email
    contact_phone = Column(String(20), nullable=True)  # Телефон (опционально)
    additional_info = Column(Text, nullable=True)  # Дополнительная информация

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    # Связь с таблицей Company
    company = relationship("Company", back_populates="info")

# Таблица Campaigns
class Campaigns(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    campaign_name = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String, default="active", nullable=False)
    status_for_user = Column(Boolean, default=True, nullable=False)  # Новая колонка
    params = Column(JSON, nullable=True)  # Поле для хранения параметров

    templates = relationship("Templates", back_populates="campaign")
    company = relationship("Company", back_populates="campaigns")

# Таблица EmailTables
class EmailTables(Base):
    __tablename__ = "email_tables"

    email_table_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    telegram_id = Column(String, nullable=False)
    upload_date = Column(DateTime, default=func.now(), nullable=False)
    table_name = Column(String, nullable=False)
    status = Column(String, default="uploaded", nullable=False)
    row_count = Column(Integer, nullable=False)

# Таблица EmailSegmentation
class EmailSegmentation(Base):
    __tablename__ = "email_segmentation"

    email_segment_id = Column(Integer, primary_key=True, autoincrement=True)
    email_table_id = Column(Integer, ForeignKey("email_tables.email_table_id"), nullable=False)
    region = Column(String, nullable=True)
    interest = Column(String, nullable=True)
    contact_email = Column(String, nullable=False)
    contact_name = Column(String, nullable=True)
    company_name = Column(String, nullable=True)

# Таблица Templates
class Templates(Base):
    __tablename__ = "templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    content_plan = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    campaign = relationship("Campaigns", back_populates="templates")

# Таблица MailingSettings
class MailingSettings(Base):
    __tablename__ = "mailing_settings"

    settings_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    schedule = Column(String, nullable=False)
    customization_level = Column(String, nullable=True)
    template_id = Column(Integer, ForeignKey("templates.template_id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

# Таблица LeadResponses
class LeadResponses(Base):
    __tablename__ = "lead_responses"

    response_id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("email_segmentation.email_segment_id"), nullable=False)
    received_at = Column(DateTime, default=func.now(), nullable=False)
    sender_email = Column(String, nullable=False)
    warmth_score = Column(Integer, nullable=True)
    status = Column(String, default="unprocessed", nullable=False)

# Таблица ResponseSettings
class ResponseSettings(Base):
    __tablename__ = "response_settings"

    response_settings_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    auto_reply = Column(Boolean, default=False, nullable=False)
    draft_reply = Column(Boolean, default=False, nullable=False)
    notification_only = Column(Boolean, default=False, nullable=False)
    no_notification = Column(Boolean, default=False, nullable=False)