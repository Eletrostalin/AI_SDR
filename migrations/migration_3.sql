DO $$ DECLARE
    r RECORD;
BEGIN
    -- Удалить все таблицы, кроме migrations
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'migrations') LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    END LOOP;
END $$;