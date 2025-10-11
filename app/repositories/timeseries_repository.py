# app/repositories/timeseries_repository.py 

from redis import Redis
from app.core import logger
from typing import Dict

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _create_ts_if_not_exists(self, key: str, labels: Dict):
        """Función interna para crear una serie de tiempo si no existe."""
        try:
            # Intenta obtener información de la serie; si falla, no existe.
            self.redis.ts().info(key)
        except Exception:
            self.redis.ts().create(key, labels=labels)
            logger.info(f"Serie de tiempo creada: {key}")

    def add_measurements(self, user_id: int, device_id: int, watts: float, volts: float, amps: float):
        """
        Añade las mediciones de potencia, voltaje y amperaje a sus respectivas series temporales.
        """
        try:
            timestamp = '*'  # Usar el timestamp actual del servidor Redis

            # Definir claves y etiquetas para cada métrica
            keys_and_labels = {
                f"ts:user:{user_id}:device:{device_id}:watts": {"metric": "power", "unit": "W"},
                f"ts:user:{user_id}:device:{device_id}:volts": {"metric": "voltage", "unit": "V"},
                f"ts:user:{user_id}:device:{device_id}:amps": {"metric": "current", "unit": "A"},
            }

            # Crear las series de tiempo si no existen
            for key, labels in keys_and_labels.items():
                all_labels = {"user_id": user_id, "device_id": device_id, **labels}
                self._create_ts_if_not_exists(key, all_labels)

            # Usar un pipeline para añadir todas las mediciones de forma atómica (más eficiente)
            pipe = self.redis.ts().pipeline()
            pipe.add(keys_and_labels.popitem()[0], timestamp, watts)
            pipe.add(keys_and_labels.popitem()[0], timestamp, volts)
            pipe.add(keys_and_labels.popitem()[0], timestamp, amps)
            pipe.execute()

            logger.info(f"Mediciones añadidas para user:{user_id}, device:{device_id} (W:{watts}, V:{volts}, A:{amps})")

        except Exception as e:
            logger.error(f"Error al añadir mediciones a Redis para user:{user_id}, device:{device_id}: {e}")