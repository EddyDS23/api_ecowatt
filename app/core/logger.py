import logging
from logging.handlers import RotatingFileHandler
import os 

if not os.path.exists("logs"):
    os.makedirs("logs")

handler = RotatingFileHandler("logs/app_debug.log",maxBytes=5_000_000,backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger("ecowatt_logger")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.propagate=True