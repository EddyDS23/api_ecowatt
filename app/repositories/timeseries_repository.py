# app/repositories/timeseries_repository.py 

from datetime import datetime, timezone
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

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis con timestamp.
        Soporta RedisTimeSeries (si está habilitado); si no, usa un ZSET como fallback.
        """
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)  # siempre en milisegundos
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # Si tienes módulo RedisTimeSeries disponible
            if hasattr(self.redis, "ts"):
                # Crear series si no existen
                for key, label in [
                    (key_watts, "watts"),
                    (key_volts, "volts"),
                    (key_amps, "amps"),
                ]:
                    try:
                        self.redis.ts().create(
                            key,
                            labels={
                                "user_id": str(user_id),
                                "device_id": str(device_id),
                                "type": label,
                            },
                        )
                    except Exception:
                        # ya existe, lo ignoramos
                        pass

                pipe = self.redis.ts().pipeline()
                pipe.add(key_watts, timestamp, watts)
                pipe.add(key_volts, timestamp, volts)
                pipe.add(key_amps, timestamp, amps)
                pipe.execute()

            else:
                # Si no tienes RedisTimeSeries, usar fallback con ZSET
                pipe = self.redis.pipeline()
                pipe.zadd(key_watts, {str(watts): timestamp})
                pipe.zadd(key_volts, {str(volts): timestamp})
                pipe.zadd(key_amps,  {str(amps): timestamp})
                pipe.execute()

        except Exception as e:
            print(f"❌ Error al guardar datos en Redis: {e}")