from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base
from config import DATABASE_URL

# Создаём движок базы данных
engine = create_engine(DATABASE_URL)

# Создаём фабрику сессий
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Создаём таблицы, если их ещё нет
def init_db():
    Base.metadata.create_all(bind=engine)