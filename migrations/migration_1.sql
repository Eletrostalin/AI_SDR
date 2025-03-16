-- Создание таблиц с учетом связей и последовательности создания:

-- companies (нет внешних ключей, создаём первой)
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    chat_id VARCHAR NOT NULL UNIQUE,
    telegram_id VARCHAR NOT NULL,
    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    name VARCHAR,
    google_sheet_url VARCHAR,
    google_sheet_name VARCHAR
);

-- users (зависит от companies)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    telegram_id VARCHAR NOT NULL UNIQUE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    company_id INTEGER REFERENCES companies(company_id),
    name VARCHAR
);

-- email_tables (зависит от companies)
CREATE TABLE email_tables (
    email_table_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    table_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- chat_threads (нет жёстких обязательных внешних ключей на текущем этапе)
CREATE TABLE chat_threads (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL UNIQUE,
    thread_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- campaigns (зависит от companies, email_tables, chat_threads)
CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    thread_id BIGINT NOT NULL REFERENCES chat_threads(thread_id) ON DELETE CASCADE UNIQUE,
    campaign_name VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR DEFAULT 'active' NOT NULL,
    status_for_user BOOLEAN DEFAULT TRUE NOT NULL,
    filters JSONB,
    email_table_id INTEGER REFERENCES email_tables(email_table_id)
);

-- company_info (зависит от companies)
CREATE TABLE company_info (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE UNIQUE,
    company_name VARCHAR NOT NULL,
    company_mission TEXT,
    company_values TEXT,
    business_sector TEXT,
    office_addresses_and_hours TEXT,
    resource_links TEXT,
    target_audience_b2b_b2c_niche_geography TEXT,
    unique_selling_proposition TEXT,
    customer_pain_points TEXT,
    competitor_differences TEXT,
    promoted_products_and_services TEXT,
    delivery_availability_geographical_coverage TEXT,
    frequently_asked_questions_with_answers TEXT,
    common_customer_objections_and_responses TEXT,
    successful_case_studies TEXT,
    additional_information TEXT,
    missing_field_feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- content_plans (зависит от companies и campaigns)
CREATE TABLE content_plans (
    content_plan_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    telegram_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    wave_count INTEGER DEFAULT 0 NOT NULL,
    description TEXT
);

-- waves (зависит от content_plans, campaigns, companies)
CREATE TABLE waves (
    wave_id SERIAL PRIMARY KEY,
    content_plan_id INTEGER NOT NULL REFERENCES content_plans(content_plan_id),
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    company_id INTEGER NOT NULL REFERENCES companies(company_id),
    send_date TIMESTAMP NOT NULL,
    subject VARCHAR NOT NULL
);

-- templates (зависит от companies, campaigns, waves)
CREATE TABLE templates (
    template_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    wave_id INTEGER REFERENCES waves(wave_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    subject VARCHAR NOT NULL,
    user_request TEXT NOT NULL,
    template_content TEXT NOT NULL
);

-- email_connections (зависит от companies)
CREATE TABLE email_connections (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    login VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    smtp_server VARCHAR NOT NULL,
    smtp_port INTEGER NOT NULL,
    imap_server VARCHAR NOT NULL,
    imap_port INTEGER NOT NULL,
    creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- migrations (нет внешних ключей, создаём последней или отдельно)
CREATE TABLE migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);