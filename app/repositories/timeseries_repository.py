# app/repositories/timeseries_repository.py 

from datetime import datetime, timezone
from redis import Redis
from app.core import logger
from typing import Dict

# Cache GLOBAL (compartido entre todas las instancias del repositorio)
_GLOBAL_CREATED_SERIES = set()

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _ensure_ts_exists(self, key: str, labels: Dict):
        """
        Crea la serie de tiempo solo si no existe.
        Usa un cache GLOBAL en memoria compartido entre todas las instancias.
        """
        # Si ya lo creamos en CUALQUIER instancia, skip
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
            # Verificar si existe en Redis
            self.redis.ts().info(key)
            # Si llegamos aquí, la serie ya existe
            self._created_series.add(key)
            logger.debug(f"Serie ya existente detectada: {key}")
        except Exception:
            # No existe, intentar crear
            try:
                self.redis.ts().create(key, labels=labels)
                self._created_series.add(key)
                logger.info(f"Serie de tiempo creada: {key}")
            except Exception as e:
                # Posible race condition: otra instancia la creó justo ahora
                # Intentar agregarla al cache de todas formas
                try:
                    self.redis.ts().info(key)
                    self._created_series.add(key)
                except Exception:
                    logger.error(f"No se pudo crear ni verificar la serie {key}: {e}")

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis con timestamp.
        Soporta RedisTimeSeries (recomendado). Si no está, usa un ZSET como fallback.
        """
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)  # siempre en milisegundos
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # Si tienes módulo RedisTimeSeries disponible
            if hasattr(self.redis, "ts"):
                # Asegurar que las series existen (solo la primera vez por serie)
                self._ensure_ts_exists(key_watts, {
                    "user_id": str(user_id),
                    "device_id": str(device_id),
                    "type": "watts"
                })
                self._ensure_ts_exists(key_volts, {
                    "user_id": str(user_id),
                    "device_id": str(device_id),
                    "type": "volts"
                })
                self._ensure_ts_exists(key_amps, {
                    "user_id": str(user_id),
                    "device_id": str(device_id),
                    "type": "amps"
                })

                # Insertar los datos usando pipeline para eficiencia
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
            logger.error(f"❌ Error al guardar datos en Redis: {e}")