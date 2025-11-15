# app/repositories/timeseries_repository.py (SOLUCIÓN DEFINITIVA)

from datetime import datetime, timezone
from redis import Redis
from app.core import logger
from typing import Dict

# Cache GLOBAL para evitar verificaciones repetidas
_GLOBAL_CREATED_SERIES = set()

# ✅ CONSTANTE ÚNICA para retention (30 días en milisegundos)
RETENTION_MS = 2592000000  # 30 días

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _ensure_ts_exists(self, key: str, labels: Dict):
        """
        Crea la serie de tiempo solo si no existe.
        
        🔥 FIX CRÍTICO:
        1. USA UNA SOLA CONSTANTE para retention (no compara con valores diferentes)
        2. NO altera series existentes (evita resetear chunks)
        3. Solo verifica una vez por sesión (cache global)
        """
        
        # Si ya verificamos esta serie en esta sesión, saltamos
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
            # Verificar si la serie existe en Redis
            info = self.redis.ts().info(key)
            
            # ✅ Serie existe, solo la agregamos al cache
            _GLOBAL_CREATED_SERIES.add(key)
            logger.debug(f"✅ Serie verificada: {key}")
            
            # 🔥 FIX: NO ALTERAR SERIES EXISTENTES
            # Comentamos la lógica de TS.ALTER porque resetea chunks
            # Si necesitas cambiar retention, hazlo manualmente con Redis CLI
            
            return
            
        except Exception as check_error:
            # Serie NO existe, la creamos
            try:
                logger.info(f"📝 Creando nueva serie: {key}")
                
                # ✅ Crear con retention consistente
                self.redis.execute_command(
                    'TS.CREATE',
                    key,
                    'DUPLICATE_POLICY', 'LAST',
                    'RETENTION', str(RETENTION_MS),  # Usa la constante
                    'LABELS',
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
                
                _GLOBAL_CREATED_SERIES.add(key)
                logger.info(
                    f"✅ Serie creada: {key} "
                    f"(RETENTION: {RETENTION_MS}ms = 30 días, DUPLICATE_POLICY: LAST)"
                )
                
            except Exception as create_error:
                error_msg = str(create_error).lower()
                
                if "already exists" in error_msg or "tsdb: key already exists" in error_msg:
                    # Otra instancia/worker la creó (race condition normal en multi-worker)
                    _GLOBAL_CREATED_SERIES.add(key)
                    logger.debug(f"✅ Serie creada por otro worker: {key}")
                else:
                    logger.error(f"❌ Error creando serie {key}: {create_error}")

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis TimeSeries.
        
        🔥 OPTIMIZADO:
        - Usa timestamps UTC actuales
        - Verifica series una sola vez por sesión
        - Timestamps incrementales para evitar duplicados
        """
        # Generar timestamp UTC actual
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # ✅ Asegurar que las series existan (solo primera vez)
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

            # ✅ Insertar datos (timestamps incrementales para evitar duplicados)
            self.redis.execute_command('TS.ADD', key_watts, base_timestamp, watts)
            self.redis.execute_command('TS.ADD', key_volts, base_timestamp + 1, volts)
            self.redis.execute_command('TS.ADD', key_amps, base_timestamp + 2, amps)
            
            logger.debug(
                f"💾 Datos guardados: user={user_id}, device={device_id}, "
                f"ts={base_timestamp}, watts={watts}W"
            )

        except Exception as e:
            logger.error(
                f"❌ Error guardando datos para device {device_id}: {e}"
            )


# 🔧 FUNCIÓN DE UTILIDAD para resetear cache (debugging)
def clear_series_cache():
    """
    Limpia el cache de series verificadas.
    Útil si reinicias Redis o necesitas forzar re-verificación.
    """
    global _GLOBAL_CREATED_SERIES
    _GLOBAL_CREATED_SERIES.clear()
    logger.info("🔄 Cache de series limpiado")