import logging
from logging.handlers import RotatingFileHandler
from .discord_logger import send_discord_alert
import os

# Carpeta de logs (fuera del código fuente)
LOG_DIR = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "backend.log")

logger = logging.getLogger("ecowatt")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10_000_000, backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

def log_critical_error(msg: str):
    """Guarda en logs y manda alerta a Discord."""
    import logging
    logger = logging.getLogger("ecowatt")
    logger.error(msg)
    send_discord_alert(msg)
