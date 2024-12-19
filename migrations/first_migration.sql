-- Таблица для миграций
CREATE TABLE IF NOT EXISTS migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Таблица компаний
CREATE TABLE IF NOT EXISTS companies (
    company_id SERIAL PRIMARY KEY,
    chat_id VARCHAR NOT NULL UNIQUE,
    telegram_id VARCHAR NOT NULL,
    creation_date TIMESTAMP DEFAULT now() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    name VARCHAR
);

-- Таблица информации о компании
CREATE TABLE IF NOT EXISTS company_info (
    company_info_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20),
    additional_info TEXT,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    telegram_id VARCHAR NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT now() NOT NULL,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    name VARCHAR
);

-- Таблица потоков чата
CREATE TABLE IF NOT EXISTS chat_threads (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Таблица кампаний
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    thread_id BIGINT NOT NULL REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
    campaign_name VARCHAR NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    status_for_user BOOLEAN DEFAULT TRUE NOT NULL,
    params JSON
);

-- Таблица шаблонов
CREATE TABLE IF NOT EXISTS templates (
    template_id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    content_plan VARCHAR,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Таблица контентных планов
CREATE TABLE IF NOT EXISTS content_plans (
    content_plan_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    telegram_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    wave_count INTEGER DEFAULT 0 NOT NULL,
    description TEXT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE
);

-- Таблица волн
CREATE TABLE IF NOT EXISTS waves (
    wave_id SERIAL PRIMARY KEY,
    content_plan_id INTEGER NOT NULL REFERENCES content_plans(content_plan_id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    send_time TIMESTAMP NOT NULL,
    send_date TIMESTAMP NOT NULL,
    subject VARCHAR NOT NULL,
    template_id INTEGER REFERENCES templates(template_id) ON DELETE CASCADE
);

-- Таблица email-таблиц
CREATE TABLE IF NOT EXISTS email_tables (
    email_table_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    table_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

-- Таблица сегментов email
CREATE TABLE IF NOT EXISTS email_segments (
    email_id SERIAL PRIMARY KEY,
    email_table_name VARCHAR NOT NULL REFERENCES email_tables(table_name) ON DELETE CASCADE,
    name VARCHAR,
    tax_id VARCHAR,
    registration_date VARCHAR,
    address VARCHAR,
    region VARCHAR,
    status VARCHAR,
    msp_registry VARCHAR,
    director_name VARCHAR,
    director_position VARCHAR,
    phone_number VARCHAR,
    email VARCHAR,
    website VARCHAR,
    primary_activity VARCHAR,
    other_activities VARCHAR,
    licenses VARCHAR,
    revenue VARCHAR,
    balance VARCHAR,
    net_profit_or_loss VARCHAR,
    arbitration_defendant VARCHAR,
    employee_count VARCHAR,
    branch_count VARCHAR
);