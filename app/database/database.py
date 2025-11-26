# app/database/database.py 

from app.core import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import redis
from app.core import logger

# --- Configuración de PostgreSQL ---
Base = declarative_base()

engine = create_engine(
    settings.URL_DATABASE_SQL,
    pool_size=5,           # Aumentamos el número de conexiones base a 20
    max_overflow=3,        # Mantenemos el overflow
    pool_timeout=30,       # Tiempo de espera
    pool_recycle=3600,     #Reutilizar conexiones
    pool_pre_ping=True     # Verifica que la conexión esté viva antes de usarla
)

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