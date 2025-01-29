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
    telegram_id = Column(BigInteger, nullable=False, unique=True, index=True)
    added_at = Column(DateTime, default=func.now(), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False)
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
    chat_id = Column(BigInteger, nullable=False, unique=True)
    telegram_id = Column(BigInteger, nullable=False)
    creation_date = Column(DateTime, default=func.now(), nullable=False)
    status = Column(Boolean, default=True, nullable=False)  # Теперь булево (True = активен)
    name = Column(String, nullable=True)

    # Связи
    info = relationship("CompanyInfo", back_populates="company", uselist=False)
    campaigns = relationship("Campaigns", back_populates="company")
    users = relationship("User", back_populates="company")
    content_plans = relationship("ContentPlan", back_populates="company")
    waves = relationship("Waves", back_populates="company")
    templates = relationship("Templates", back_populates="company")


class CompanyInfo(Base):
    __tablename__ = "company_info"

    company_info_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(255), nullable=False)
    region = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(20), nullable=True)
    additional_info = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Связь с Company
    company = relationship("Company", back_populates="info")


class Campaigns(Base):
    __tablename__ = "campaigns"

    campaign_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    thread_id = Column(BigInteger, ForeignKey("chat_threads.thread_id", ondelete="CASCADE"), nullable=False,
                       unique=True)
    campaign_name = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(Boolean, default=True, nullable=False)  # Теперь булево
    status_for_user = Column(Boolean, default=True, nullable=False)
    params = Column(JSONB, nullable=True)  # JSON → JSONB
    segments = Column(JSONB, nullable=True)  # JSON → JSONB

    # Связи
    templates = relationship("Templates", back_populates="campaign")
    content_plans = relationship("ContentPlan", back_populates="campaign")
    waves = relationship("Waves", back_populates="campaign")
    company = relationship("Company", back_populates="campaigns")
    chat_thread = relationship("ChatThread", backref="campaigns")


class EmailTable(Base):
    __tablename__ = "email_tables"

    email_table_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    table_name = Column(String, nullable=False, unique=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class ContentPlan(Base):
    __tablename__ = "content_plans"

    content_plan_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    telegram_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    wave_count = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)

    # Связи
    waves = relationship("Waves", back_populates="content_plan")
    company = relationship("Company", back_populates="content_plans")
    campaign = relationship("Campaigns", back_populates="content_plans")


class Waves(Base):
    __tablename__ = "waves"

    wave_id = Column(Integer, primary_key=True, autoincrement=True)
    content_plan_id = Column(Integer, ForeignKey("content_plans.content_plan_id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    send_time = Column(DateTime, nullable=False)
    send_date = Column(DateTime, nullable=False)
    subject = Column(String, nullable=False)

    # Связи
    content_plan = relationship("ContentPlan", back_populates="waves")
    campaign = relationship("Campaigns", back_populates="waves")
    company = relationship("Company", back_populates="waves")
    template = relationship("Templates", uselist=False, back_populates="wave")


class Templates(Base):
    __tablename__ = "templates"

    template_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.campaign_id"), nullable=False)
    wave_id = Column(Integer, ForeignKey("waves.wave_id"), nullable=False, unique=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    subject = Column(String, nullable=False)
    user_request = Column(Text, nullable=False)
    template_content = Column(Text, nullable=False)
    status = Column(Boolean, default=True, nullable=False)  # Теперь булево

    # Связь с Company и Campaign
    company = relationship("Company", back_populates="templates")
    campaign = relationship("Campaigns", back_populates="templates")
    wave = relationship("Waves", back_populates="template")


class Migration(Base):
    """
    Таблица для хранения информации о применённых миграциях.
    """
    __tablename__ = "migrations"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный идентификатор
    migration_name = Column(String, nullable=False, unique=True)  # Имя файла миграции
    applied_at = Column(DateTime, default=func.now(), nullable=False)  # Время применения