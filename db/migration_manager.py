import os
import logging
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

from db.models import Migration

DATABASE_URL = 'postgresql://postgres:13579033@localhost:5432/AI_SDR_stage'
engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)


def check_tables_exist():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migrations');")
        )
        return result.scalar()


def apply_migrations():
    migrations_folder = 'migrations'

    # Проверка наличия таблицы
    tables_exist = check_tables_exist()

    with Session() as session:
        if tables_exist:
            result = session.execute(select(Migration.migration_name))
            applied_migrations = set(row[0] for row in result.all())
        else:
            applied_migrations = set()
            logging.info("Таблицы не найдены. Применение первой миграции.")

        all_migrations = [f for f in os.listdir(migrations_folder) if f.endswith('.sql')]
        new_migrations = [m for m in all_migrations if m not in applied_migrations]
        new_migrations.sort()

        if new_migrations:
            logging.info(f"Найдено {len(new_migrations)} новых миграций: {new_migrations}")
            with engine.begin() as connection:  # Контекст управления транзакциями
                try:
                    for migration in new_migrations:
                        with open(os.path.join(migrations_folder, migration), 'r', encoding='utf-8') as file:
                            sql_commands = file.read()
                        for command in sql_commands.split(';'):
                            command = command.strip()
                            if command:
                                logging.info(f"Применение SQL команды:\n{command}")
                                connection.execute(text(command))

                    for migration in new_migrations:
                        session.add(Migration(migration_name=migration))
                    session.commit()
                    logging.info(f"Миграции {new_migrations} успешно применены.")
                except Exception as e:
                    logging.error(f"Ошибка при применении миграции: {e}")
                    raise
        else:
            logging.info("Новые миграции отсутствуют.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_migrations()