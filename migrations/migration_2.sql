
-- Создание таблицы segment_summary
CREATE TABLE segment_summary (
    segment_id SERIAL PRIMARY KEY, -- Уникальный ID сегмента
    company_id INTEGER NOT NULL, -- Привязка к компании
    segment_table_name VARCHAR NOT NULL UNIQUE, -- Имя таблицы сегмента
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, -- Дата создания
    status VARCHAR DEFAULT 'active' NOT NULL, -- Статус (active, deleted)
    description TEXT, -- Описание сегмента
    params JSON, -- Параметры сегментации (запрос и фильтры)

    -- Связь с таблицей companies
    CONSTRAINT fk_company FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
);

-- Обновление таблицы companies для добавления связи с сегментами
-- (если в коде эта связь уже есть, дополнительно ничего не требуется)
-- Здесь автоматически поддерживается relationship через SQLAlchemy.