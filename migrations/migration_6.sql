-- Удаление таблиц с учётом зависимостей
DROP TABLE IF EXISTS waves CASCADE;
DROP TABLE IF EXISTS templates CASCADE;
DROP TABLE IF EXISTS content_plans CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS chat_threads CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS company_info CASCADE;
DROP TABLE IF EXISTS companies CASCADE;

-- Создание таблиц
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    chat_id VARCHAR(255) NOT NULL UNIQUE,
    telegram_id VARCHAR(255) NOT NULL,
    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    name VARCHAR(255)
);

CREATE TABLE company_info (
    company_info_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    industry VARCHAR(255) NOT NULL,
    region VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(20),
    additional_info TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id VARCHAR(255) NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE SET NULL,
    name VARCHAR(255)
);

CREATE TABLE chat_threads (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    thread_id BIGINT REFERENCES chat_threads(thread_id) ON DELETE CASCADE NOT NULL UNIQUE,
    campaign_name VARCHAR(255) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    status_for_user BOOLEAN DEFAULT TRUE NOT NULL,
    params JSON,
    segments JSONB
);

CREATE TABLE content_plans (
    content_plan_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    telegram_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    wave_count INTEGER DEFAULT 0 NOT NULL,
    description TEXT,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE NOT NULL
);

CREATE TABLE templates (
    template_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    subject VARCHAR(255) NOT NULL,
    user_request TEXT NOT NULL,
    template_content TEXT NOT NULL
);

CREATE TABLE waves (
    wave_id SERIAL PRIMARY KEY,
    content_plan_id INTEGER REFERENCES content_plans(content_plan_id) ON DELETE CASCADE NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE CASCADE NOT NULL,
    send_time TIMESTAMP NOT NULL,
    send_date TIMESTAMP NOT NULL,
    subject VARCHAR(255) NOT NULL,
    template_id INTEGER REFERENCES templates(template_id) ON DELETE SET NULL
);