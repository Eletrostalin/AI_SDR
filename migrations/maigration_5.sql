CREATE TABLE email_tables (
    email_table_id SERIAL PRIMARY KEY,                  -- Уникальный идентификатор записи
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE, -- Внешний ключ на companies
    table_name VARCHAR NOT NULL UNIQUE,                -- Уникальное имя таблицы
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,       -- Дата создания записи
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL        -- Дата обновления записи
);