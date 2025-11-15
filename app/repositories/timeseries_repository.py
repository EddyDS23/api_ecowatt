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
        - Orden correcto de parámetros TS.CREATE
        - RETENTION y DUPLICATE_POLICY antes de LABELS
        """
        
        # Si ya verificamos esta serie en esta sesión, saltamos
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
            # Verificar si la serie existe en Redis
            info = self.redis.ts().info(key)
            
            # ✅ Serie existe, validar configuración
            current_retention = info.get('retentionTime', 0)
            current_dup_policy = info.get('duplicatePolicy')
            
            # 🔥 FIX: Si la configuración está incorrecta, alertar
            if current_retention != RETENTION_MS or current_dup_policy != 'last':
                logger.warning(
                    f"⚠️ Serie {key} tiene configuración incorrecta: "
                    f"retention={current_retention} (esperado: {RETENTION_MS}), "
                    f"dup_policy={current_dup_policy} (esperado: last)"
                )
                
                # Intentar corregir con TS.ALTER
                try:
                    if current_retention != RETENTION_MS:
                        self.redis.execute_command(
                            'TS.ALTER', key, 
                            'RETENTION', str(RETENTION_MS)
                        )
                        logger.info(f"✅ Retention corregido para {key}")
                    
                    if current_dup_policy != 'last':
                        self.redis.execute_command(
                            'TS.ALTER', key,
                            'DUPLICATE_POLICY', 'LAST'
                        )
                        logger.info(f"✅ Duplicate policy corregido para {key}")
                        
                except Exception as alter_error:
                    logger.error(f"❌ No se pudo corregir configuración de {key}: {alter_error}")
            
            _GLOBAL_CREATED_SERIES.add(key)
            logger.debug(f"✅ Serie verificada: {key}")
            return
            
        except Exception as check_error:
            # Serie NO existe, la creamos
            try:
                logger.info(f"📝 Creando nueva serie: {key}")
                
                # 🔥 FIX CRÍTICO: ORDEN CORRECTO DE PARÁMETROS
                # En RedisTimeSeries, el orden ES IMPORTANTE:
                # TS.CREATE key [RETENTION ms] [ENCODING <encoding>] [CHUNK_SIZE size] 
                #           [DUPLICATE_POLICY policy] [LABELS label value...]
                
                self.redis.execute_command(
                    'TS.CREATE', key,
                    'RETENTION', str(RETENTION_MS),          # ✅ PRIMERO
                    'DUPLICATE_POLICY', 'LAST',              # ✅ SEGUNDO
                    'LABELS',                                # ✅ AL FINAL
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
                
                _GLOBAL_CREATED_SERIES.add(key)
                
                # Verificar que se creó correctamente
                verify_info = self.redis.ts().info(key)
                verify_retention = verify_info.get('retentionTime', 0)
                verify_dup_policy = verify_info.get('duplicatePolicy')
                
                logger.info(
                    f"✅ Serie creada: {key}\n"
                    f"   - RETENTION: {verify_retention}ms ({verify_retention / 86400000:.1f} días)\n"
                    f"   - DUPLICATE_POLICY: {verify_dup_policy}"
                )
                
                # Validar que se creó con la config correcta
                if verify_retention != RETENTION_MS:
                    logger.error(
                        f"❌ ADVERTENCIA: Serie creada con retention incorrecto: "
                        f"{verify_retention} (esperado: {RETENTION_MS})"
                    )
                
            except Exception as create_error:
                error_msg = str(create_error).lower()
                
                if "already exists" in error_msg or "tsdb: key already exists" in error_msg:
                    # Otra instancia la creó (race condition normal)
                    _GLOBAL_CREATED_SERIES.add(key)
                    logger.debug(f"✅ Serie creada por otro worker: {key}")
                else:
                    logger.error(f"❌ Error creando serie {key}: {create_error}")

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis TimeSeries.
        """
        # Generar timestamp UTC actual
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # ✅ Asegurar que las series existan con la config correcta
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

            # ✅ Insertar datos
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