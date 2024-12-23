-- Удаление внешнего ключа, если он существует
ALTER TABLE email_tables DROP CONSTRAINT IF EXISTS email_tables_email_segments_fkey;

-- Удаление таблицы сегментов, если она больше не нужна
DROP TABLE IF EXISTS email_segments;

-- Добавление колонки segments в таблицу campaigns
ALTER TABLE campaigns ADD COLUMN segments JSONB;