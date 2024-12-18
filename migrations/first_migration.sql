-- Таблица companies
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    chat_id VARCHAR NOT NULL UNIQUE,
    telegram_id VARCHAR NOT NULL,
    creation_date TIMESTAMP DEFAULT now() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    name VARCHAR
);

-- Таблица chat_threads
CREATE TABLE chat_threads (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);

-- Таблица campaigns
CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    thread_id BIGINT REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
    campaign_name VARCHAR NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    status_for_user BOOLEAN DEFAULT TRUE NOT NULL,
    params JSON
);

-- Таблица users
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id VARCHAR NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT now() NOT NULL,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    name VARCHAR
);

-- Таблица company_info
CREATE TABLE company_info (
    company_info_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20),
    additional_info TEXT,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

-- Таблица content_plans
CREATE TABLE content_plans (
    content_plan_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    telegram_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    wave_count INTEGER DEFAULT 0 NOT NULL,
    description TEXT,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE
);

-- Таблица waves
CREATE TABLE waves (
    wave_id SERIAL PRIMARY KEY,
    content_plan_id INTEGER REFERENCES content_plans(content_plan_id) ON DELETE CASCADE,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    send_time TIMESTAMP NOT NULL,
    send_date TIMESTAMP NOT NULL,
    subject VARCHAR NOT NULL,
    template_id INTEGER
);

-- Таблица email_tables
CREATE TABLE email_tables (
    email_table_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    table_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now()
);

-- Таблица templates
CREATE TABLE templates (
    template_id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE,
    content_plan VARCHAR,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now() NOT NULL
);


CREATE TABLE IF NOT EXISTS migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);