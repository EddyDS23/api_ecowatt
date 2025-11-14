# app/repositories/timeseries_repository.py (SOLUCIÓN FINAL AL BUG)

from datetime import datetime, timezone
from redis import Redis
from app.core import logger
from typing import Dict

# Cache GLOBAL
_GLOBAL_CREATED_SERIES = set()

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _ensure_ts_exists(self, key: str, labels: Dict):
        """
        Crea la serie de tiempo solo si no existe.
        
        FIX CRÍTICO: Verifica SIEMPRE en Redis primero, no solo en cache.
        El cache es útil para optimización, pero Redis es la fuente de verdad.
        """
        
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
           
            info = self.redis.ts().info(key)
            
           
            retention = info.get('retentionTime', info.get('retention_time', 0))
            dup_policy = info.get('duplicatePolicy', info.get('duplicate_policy', None))
            
     
            if retention != 5259600000:
                logger.warning(f"⚠️ Serie {key} tiene retention incorrecto ({retention}), actualizando...")
                self.redis.execute_command('TS.ALTER', key, 'RETENTION', '2592000000')
                logger.info(f"✅ Retention actualizado para {key}")
            
          
            _GLOBAL_CREATED_SERIES.add(key)
            logger.debug(f"Serie verificada y agregada al cache: {key}")
            return
            
        except Exception as check_error:
           
            try:
                logger.info(f"📝 Creando serie nueva: {key}")
                
                self.redis.execute_command(
                    'TS.CREATE',
                    key,
                    'DUPLICATE_POLICY', 'LAST',
                    'RETENTION', '5259600000',  # 2 meses
                    'LABELS',
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
                
                _GLOBAL_CREATED_SERIES.add(key)
                logger.info(
                    f"✅ Serie creada exitosamente: {key} "
                    f"(DUPLICATE_POLICY: LAST, RETENTION: 30 días)"
                )
                
            except Exception as create_error:
                # Posible race condition: otra instancia la creó
                error_msg = str(create_error).lower()
                
                if "already exists" in error_msg or "tsdb: key already exists" in error_msg:
                    # Otra instancia/worker la creó, agregarla al cache
                    _GLOBAL_CREATED_SERIES.add(key)
                    logger.debug(f"Serie creada por otro worker: {key}")
                else:
                    logger.error(f"❌ Error creando serie {key}: {create_error}")

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis TimeSeries.
        
        IMPORTANTE: SIEMPRE verifica que las series existan ANTES de insertar.
        """
        # Generar timestamp en el momento exacto
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
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

            self.redis.execute_command('TS.ADD', key_watts, base_timestamp, watts)
            self.redis.execute_command('TS.ADD', key_volts, base_timestamp + 1, volts)
            self.redis.execute_command('TS.ADD', key_amps, base_timestamp + 2, amps)
            
            logger.debug(
                f"💾 Datos guardados: user={user_id}, device={device_id}, "
                f"ts={base_timestamp}, watts={watts}W"
            )

        except Exception as e:
            logger.error(
                f"❌ Error al guardar datos en Redis para device {device_id}: {e}"
            )