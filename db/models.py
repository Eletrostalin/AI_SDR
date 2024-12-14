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


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False, unique=True)
    telegram_id = Column(String, nullable=False)
    creation_date = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String, default="active", nullable=False)
    name = Column(String, nullable=True)

    # Связи
    info = relationship("CompanyInfo", back_populates="company", uselist=False)
    campaigns = relationship("Campaigns", back_populates="company")
    users = relationship("User", back_populates="company")
    content_plans = relationship("ContentPlan", back_populates="company")
    waves = relationship("Waves", back_populates="company")


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

    # Связь с Company
    company = relationship("Company", back_populates="info")


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

    # Связи
    templates = relationship("Templates", back_populates="campaign")
    content_plans = relationship("ContentPlan", back_populates="campaign")
    waves = relationship("Waves", back_populates="campaign")
    company = relationship("Company", back_populates="campaigns")


class EmailTable(Base):
    __tablename__ = "email_tables"

    email_table_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)  # Связь с Company
    table_name = Column(String, nullable=False, unique=True)  # Уникальное имя таблицы для каждой компании
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class ContentPlan(Base):
    __tablename__ = "content_plans"

    content_plan_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)  # Связь с Company
    telegram_id = Column(String, nullable=False)  # Telegram ID создателя
    created_at = Column(DateTime, default=func.now(), nullable=False)
    wave_count = Column(Integer, nullable=False, default=0)  # Количество волн
    description = Column(Text, nullable=True)  # Описание контентного плана
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)  # Связь с Campaigns

    # Связи
    waves = relationship("Waves", back_populates="content_plan")
    company = relationship("Company", back_populates="content_plans")
    campaign = relationship("Campaigns", back_populates="content_plans")


class Waves(Base):
    __tablename__ = "waves"

    wave_id = Column(Integer, primary_key=True, autoincrement=True)
    content_plan_id = Column(Integer, ForeignKey("content_plans.content_plan_id"), nullable=False)  # Связь с ContentPlan
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=True)  # Связь с Campaigns
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)  # Связь с Company
    send_time = Column(DateTime, nullable=False)  # Время отправки
    send_date = Column(DateTime, nullable=False)  # Дата отправки
    subject = Column(String, nullable=False)  # Тема
    template_id = Column(Integer, ForeignKey("templates.template_id"), nullable=True)  # ID шаблона

    # Связи
    content_plan = relationship("ContentPlan", back_populates="waves")
    campaign = relationship("Campaigns", back_populates="waves")
    company = relationship("Company", back_populates="waves")


class Templates(Base):
    __tablename__ = "templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    content_plan = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Связь с Campaigns
    campaign = relationship("Campaigns", back_populates="templates")