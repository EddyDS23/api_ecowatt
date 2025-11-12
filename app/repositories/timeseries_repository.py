# app/repositories/timeseries_repository.py (VERSIÓN FINAL)

from datetime import datetime, timezone
from redis import Redis
from app.core import logger
from typing import Dict

# Cache GLOBAL para evitar crear series múltiples veces
_GLOBAL_CREATED_SERIES = set()

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _ensure_ts_exists(self, key: str, labels: Dict):
        """
        Crea la serie de tiempo solo si no existe.
        IMPORTANTE: Ahora con DUPLICATE_POLICY y RETENTION configurados.
        """
        # Si ya verificamos que existe, skip
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
            # Verificar si ya existe en Redis
            self.redis.ts().info(key)
            # Si llegamos aquí, ya existe
            _GLOBAL_CREATED_SERIES.add(key)
            logger.debug(f"Serie existente: {key}")
            return
        except Exception:
            # No existe, crear nueva serie
            try:
                # 🔧 CONFIGURACIÓN CRÍTICA:
                # - DUPLICATE_POLICY LAST: Si llega mismo timestamp, guardar el último valor
                # - RETENTION 604800000: Retener solo 7 días (en milisegundos)
                # - LABELS: Metadata para búsquedas y organización
                
                self.redis.execute_command(
                    'TS.CREATE',
                    key,
                    'DUPLICATE_POLICY', 'LAST',        # ← Manejo de duplicados
                    'RETENTION', '2592000000',         # ← 30 días en ms (suficiente para monthly)
                    'LABELS',
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
                
                _GLOBAL_CREATED_SERIES.add(key)
                logger.info(f"✅ Serie creada: {key} (DUPLICATE_POLICY: LAST, RETENTION: 30 días)")
                
            except Exception as e:
                # Posible race condition: otra instancia la creó al mismo tiempo
                try:
                    self.redis.ts().info(key)
                    _GLOBAL_CREATED_SERIES.add(key)
                    logger.debug(f"Serie creada por otra instancia: {key}")
                except Exception:
                    logger.error(f"❌ Error creando serie {key}: {e}")

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis TimeSeries.
        
        Cambios importantes:
        - Usa execute_command en lugar de pipeline para evitar race conditions
        - Genera timestamp único en el momento exacto
        - Asegura que las series existan con configuración correcta
        """
        # 🕐 Generar timestamp en el momento EXACTO de la inserción
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # 1️⃣ Asegurar que las series existan con configuración correcta
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

            # 2️⃣ Insertar datos uno por uno (NO pipeline)
            # Usamos timestamps ligeramente diferentes (+1ms, +2ms) para garantizar unicidad
            self.redis.execute_command('TS.ADD', key_watts, base_timestamp, watts)
            self.redis.execute_command('TS.ADD', key_volts, base_timestamp + 1, volts)
            self.redis.execute_command('TS.ADD', key_amps, base_timestamp + 2, amps)
            
            logger.debug(
                f"💾 Guardado: user={user_id}, device={device_id}, "
                f"ts={base_timestamp}, watts={watts}W"
            )

        except Exception as e:
            logger.error(f"❌ Error al guardar datos en Redis para device {device_id}: {e}")