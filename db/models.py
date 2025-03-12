from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, func, BigInteger, TIMESTAMP, text
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

class EmailConnections(Base):
    __tablename__ = "email_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(BigInteger, nullable=False)

    # Новые поля вместо JSONB connection_data
    login = Column(String, nullable=False)
    password = Column(String, nullable=False)  # Можно зашифровать перед сохранением
    smtp_server = Column(String, nullable=False)
    smtp_port = Column(Integer, nullable=False)
    imap_server = Column(String, nullable=False)
    imap_port = Column(Integer, nullable=False)

    company = relationship("Company", back_populates="email_connections")

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
    templates = relationship("Templates", back_populates="company")
    email_connections = relationship("EmailConnections", back_populates="company")

class CompanyInfo(Base):
    __tablename__ = "company_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    company_name = Column(String, nullable=False)

    # New fields from the questionnaire
    company_mission = Column(Text, nullable=True)
    company_values = Column(Text, nullable=True)
    business_sector = Column(Text, nullable=True)
    office_addresses_and_hours = Column(Text, nullable=True)
    resource_links = Column(Text, nullable=True)
    target_audience_b2b_b2c_niche_geography = Column(Text, nullable=True)
    unique_selling_proposition = Column(Text, nullable=True)
    customer_pain_points = Column(Text, nullable=True)
    competitor_differences = Column(Text, nullable=True)
    promoted_products_and_services = Column(Text, nullable=True)
    delivery_availability_geographical_coverage = Column(Text, nullable=True)
    frequently_asked_questions_with_answers = Column(Text, nullable=True)
    common_customer_objections_and_responses = Column(Text, nullable=True)
    successful_case_studies = Column(Text, nullable=True)
    additional_information = Column(Text, nullable=True)
    missing_field_feedback = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    # Связь с Company
    company = relationship("Company", back_populates="info")

class Campaigns(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    thread_id = Column(BigInteger, ForeignKey("chat_threads.thread_id", ondelete="CASCADE"), nullable=False, unique=True)
    campaign_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String, default="active", nullable=False)
    status_for_user = Column(Boolean, default=True, nullable=False)
    filters = Column(JSON, nullable=True)
    email_table_id = Column(Integer, ForeignKey("email_tables.email_table_id"), nullable=True)  # Добавляем email_table_id

    # Связи
    templates = relationship("Templates", back_populates="campaign")
    content_plans = relationship("ContentPlan", back_populates="campaign")
    waves = relationship("Waves", back_populates="campaign")
    company = relationship("Company", back_populates="campaigns")
    chat_thread = relationship("ChatThread", backref="campaigns")
    email_table = relationship("EmailTable", backref="campaigns")

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
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)  # Связь с Campaigns
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)  # Связь с Company
    send_date = Column(DateTime, nullable=False)  # Дата отправки
    subject = Column(String, nullable=False)  # Тема рассылки

    # Связи
    content_plan = relationship("ContentPlan", back_populates="waves")
    campaign = relationship("Campaigns", back_populates="waves")
    company = relationship("Company", back_populates="waves")

class Templates(Base):
    __tablename__ = "templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    wave_id = Column(Integer, ForeignKey("waves.wave_id"), nullable=True)  # Добавляем wave_id
    created_at = Column(DateTime, default=func.now(), nullable=False)
    subject = Column(String, nullable=False)
    user_request = Column(Text, nullable=False)
    template_content = Column(Text, nullable=False)

    # Связи
    company = relationship("Company", back_populates="templates")
    campaign = relationship("Campaigns", back_populates="templates")
    wave = relationship("Waves", foreign_keys=[wave_id])

class Migration(Base):
    """
    Таблица для хранения информации о применённых миграциях.
    """
    __tablename__ = "migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    migration_name = Column(String, nullable=False, unique=True)  # Имя файла миграции
    applied_at = Column(DateTime, default=func.now(), nullable=False)  # Время применения