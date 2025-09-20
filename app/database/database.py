from core import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

Base = declarative_base()

engine = create_engine(settings.URL_DATABASE_SQL)

SessionLocal = sessionmaker(bind=engine,autocommit=False,autoflush=False)

def get_db():
    db:Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


