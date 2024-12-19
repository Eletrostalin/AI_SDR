import os
import logging
from sqlalchemy import select
from db.models import Migration
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text


DATABASE_URL="postgresql+psycopg://postgres:13579033@localhost:5432/AI_SDR_stage"

engine = create_async_engine(DATABASE_URL, echo=True)
# Настройка фабрики для создания асинхронных сессий
async_session = sessionmaker(
    bind=engine,            # Привязка к асинхронному движку
    class_=AsyncSession,    # Использование асинхронного класса сессий
    expire_on_commit=False  # Не сбрасывать объекты после завершения транзакций
)


async def check_tables_exist():  # Импортируй внутри функции, чтобы избежать циклического импорта
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migrations');")
            )
            return result.scalar()

async def apply_migrations():
    migrations_folder = 'migrations'

    # Проверка наличия таблиц в базе данных
    tables_exist = await check_tables_exist()

    async with async_session() as session:
        if tables_exist:
            result = await session.execute(select(Migration.migration_name))
            applied_migrations = set(row[0] for row in result.all())
        else:
            applied_migrations = set()
            logging.info("Таблицы не найдены. Применение последней миграции.")

        all_migrations = [f for f in os.listdir(migrations_folder) if f.endswith('.sql')]
        new_migrations = [m for m in all_migrations if m not in applied_migrations]
        new_migrations.sort()

        if new_migrations:
            logging.info(f"Найдено {len(new_migrations)} новых миграций: {new_migrations}")
            async with engine.connect() as conn:
                async with conn.begin():
                    try:
                        for migration in new_migrations:
                            with open(os.path.join(migrations_folder, migration), 'r', encoding='utf-8') as file:
                                sql_commands = file.read()
                            for command in sql_commands.split(';'):
                                command = command.strip()
                                if command:
                                    logging.info(f"Применение SQL команды:\n{command}")
                                    await conn.execute(text(command))
                        await conn.commit()

                        for migration in new_migrations:
                            session.add(Migration(migration_name=migration))
                        await session.commit()
                        logging.info(f"Миграции {new_migrations} успешно применены.")

                    except Exception as e:
                        logging.error(f"Ошибка при применении миграции: {e}")
                        await conn.rollback()
        else:
            logging.info("Новые миграции отсутствуют.")