-- Таблица компаний
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    chat_id VARCHAR NOT NULL UNIQUE,
    telegram_id VARCHAR NOT NULL,
    creation_date TIMESTAMP DEFAULT NOW() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    name VARCHAR
);

-- Таблица информации о компании
CREATE TABLE company_info (
    company_info_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20),
    additional_info TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Таблица пользователей
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id VARCHAR NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT NOW() NOT NULL,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE SET NULL,
    name VARCHAR
);

-- Таблица чатов и потоков
CREATE TABLE chat_threads (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Таблица кампаний
CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    thread_id BIGINT REFERENCES chat_threads(thread_id) ON DELETE CASCADE NOT NULL UNIQUE,
    campaign_name VARCHAR NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    status_for_user BOOLEAN DEFAULT TRUE NOT NULL,
    params JSON,
    segments JSONB
);

-- Таблица контентных планов
CREATE TABLE content_plans (
    content_plan_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    telegram_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    wave_count INTEGER DEFAULT 0 NOT NULL,
    description TEXT,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE NOT NULL
);

-- Таблица email-таблиц
CREATE TABLE email_tables (
    email_table_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    table_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Таблица шаблонов
CREATE TABLE templates (
    template_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    subject VARCHAR NOT NULL,
    user_request TEXT NOT NULL,
    template_content TEXT NOT NULL
);

-- Таблица волн рассылок
CREATE TABLE waves (
    wave_id SERIAL PRIMARY KEY,
    content_plan_id INTEGER REFERENCES content_plans(content_plan_id) ON DELETE CASCADE NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    send_time TIMESTAMP NOT NULL,
    send_date TIMESTAMP NOT NULL,
    subject VARCHAR NOT NULL,
    template_id INTEGER REFERENCES templates(template_id) ON DELETE SET NULL
);

-- Таблица миграций
CREATE TABLE migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_company_info
BEFORE UPDATE ON company_info
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trigger_update_email_tables
BEFORE UPDATE ON email_tables
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();