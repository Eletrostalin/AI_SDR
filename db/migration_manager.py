import os
import logging
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from db.models import Migration


# Настройка синхронного движка
engine = create_engine(DATABASE_URL, echo=True)

# Настройка фабрики для создания сессий
Session = sessionmaker(bind=engine)

def check_tables_exist():  # Синхронная проверка
    with Session() as session:
        result = session.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migrations');")
        )
        return result.scalar()

def apply_migrations():
    migrations_folder = 'migrations'

    # Проверка наличия таблиц в базе данных
    tables_exist = check_tables_exist()

    with Session() as session:
        if tables_exist:
            result = session.execute(select(Migration.migration_name))
            applied_migrations = set(row[0] for row in result.fetchall())
        else:
            applied_migrations = set()
            logging.info("Таблицы не найдены. Применение последней миграции.")

        all_migrations = [f for f in os.listdir(migrations_folder) if f.endswith('.sql')]
        new_migrations = [m for m in all_migrations if m not in applied_migrations]
        new_migrations.sort()

        if new_migrations:
            logging.info(f"Найдено {len(new_migrations)} новых миграций: {new_migrations}")
            with engine.connect() as conn:
                try:
                    for migration in new_migrations:
                        with open(os.path.join(migrations_folder, migration), 'r', encoding='utf-8') as file:
                            sql_commands = file.read()
                        for command in sql_commands.split(';'):
                            command = command.strip()
                            if command:
                                logging.info(f"Применение SQL команды:\n{command}")
                                conn.execute(text(command))
                        conn.commit()

                    for migration in new_migrations:
                        session.add(Migration(migration_name=migration))
                    session.commit()
                    logging.info(f"Миграции {new_migrations} успешно применены.")

                except Exception as e:
                    logging.error(f"Ошибка при применении миграции: {e}")
                    conn.rollback()
        else:
            logging.info("Новые миграции отсутствуют.")