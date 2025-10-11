# app/database/database.py 

from app.core import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import redis
from app.core import logger

# --- Configuración de PostgreSQL ---
Base = declarative_base()
engine = create_engine(settings.URL_DATABASE_SQL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Configuración de Redis ---
try:
    redis_client = redis.from_url(settings.URL_DATABASE_REDIS, decode_responses=True)
    redis_client.ping()
    logger.info("Conexión con Redis establecida exitosamente.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Error al conectar con Redis: {e}")
    redis_client = None

# --- Dependencia para inyectar Redis ---
def get_redis_client():
    if redis_client is None:
        raise ConnectionError("No se pudo establecer la conexión con Redis.")
    yield redis_client