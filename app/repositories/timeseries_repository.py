# app/repositories/timeseries_repository.py (MULTI-WORKER SAFE)

from datetime import datetime, timezone
from redis import Redis
from app.core import logger
from typing import Dict

# ✅ CONSTANTE ÚNICA para retention (30 días en milisegundos)
RETENTION_MS = 2592000000  # 30 días

class TimeSeriesRepository:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _ensure_ts_exists(self, key: str, labels: Dict):
        """
        Crea la serie de tiempo solo si no existe.
    
        ✅ FIXED: Verifica correctamente si la serie existe antes de crear
        """
    
        try:
            # ✅ Verificar si la serie existe
            info = self.redis.ts().info(key)
        
            # ✅ Serie existe - Validar configuración
            current_retention = info.retention_msecs
            current_dup_policy = info.duplicate_policy
        
            # Convertir bytes a string si es necesario
            if isinstance(current_dup_policy, bytes):
                current_dup_policy = current_dup_policy.decode()
        
            # Verificar configuración correcta
            config_is_correct = (
                current_retention == RETENTION_MS and 
                current_dup_policy.lower() == 'last'
            )
        
            if not config_is_correct:
                logger.warning(
                    f"⚠️ Configuración incorrecta en {key}: "
                    f"retention={current_retention}ms (esperado: {RETENTION_MS}ms), "
                    f"dup_policy={current_dup_policy} (esperado: last)"
                )      
        
            # ✅ Serie existe y está configurada - NO hacer nada más
            return
        
        except Exception as e:
            error_msg = str(e).lower()
        
            # ✅ Solo crear si el error es "no existe"
            if "does not exist" not in error_msg and "no such key" not in error_msg:
                logger.error(f"❌ Error inesperado verificando {key}: {e}")
                return  # No intentar crear si hay otro tipo de error
        
            # ✅ La serie NO existe - Crear
            try:
                logger.info(f"📝 Creando nueva serie: {key}")
            
                self.redis.execute_command(
                    'TS.CREATE', key,
                    'RETENTION', str(RETENTION_MS),
                    'DUPLICATE_POLICY', 'LAST',
                    'LABELS',
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
            
                # ✅ Verificar creación
                verify_info = self.redis.ts().info(key)
                verify_retention = verify_info.retention_msecs
                verify_dup_policy = verify_info.duplicate_policy
            
                if isinstance(verify_dup_policy, bytes):
                    verify_dup_policy = verify_dup_policy.decode()
            
                logger.info(
                    f"✅ Serie creada: {key}\n"
                    f"   • RETENTION: {verify_retention}ms ({verify_retention / 86400000:.1f} días)\n"
                    f"   • DUPLICATE_POLICY: {verify_dup_policy}"
                )
            
            except Exception as create_error:
                create_error_msg = str(create_error).lower()
            
                if "already exists" in create_error_msg or "tsdb: key already exists" in create_error_msg:
                    # Otro worker la creó justo ahora - está bien
                    logger.debug(f"✅ Serie ya existe (creada por otro worker): {key}")
                else:
                    logger.error(f"❌ Error creando serie {key}: {create_error}")
                    raise

    def add_measurements(self, user_id: int, device_id: str, watts: float, volts: float, amps: float):
        """
        Guarda las mediciones de un dispositivo en Redis TimeSeries.
        
        ✅ Multi-worker safe: Cada worker verifica en Redis antes de insertar.
        ✅ Optimización: Usa TS.MADD para insertar 3 valores en una operación.
        """
        # Generar timestamp UTC actual
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # ✅ Asegurar que las series existan
            # Cada worker verifica en Redis (no en cache local)
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

            # ✅ Insertar datos usando TS.MADD
            # Timestamps ligeramente diferentes para evitar colisiones
            self.redis.execute_command(
                'TS.MADD',
                key_watts, base_timestamp, watts,
                key_volts, base_timestamp + 1, volts,
                key_amps,  base_timestamp + 2, amps
            )
            
            logger.debug(
                f"💾 Datos guardados: user={user_id}, device={device_id}, "
                f"ts={base_timestamp}, watts={watts}W"
            )

        except Exception as e:
            logger.error(
                f"❌ Error guardando datos para device {device_id}: {e}"
            )
            # No re-lanzar - permitir que otras peticiones continúen


# 🔧 Función de utilidad para limpiar series manualmente
def delete_series(redis_client: Redis, user_id: int, device_id: int):
    """
    Elimina las series de un dispositivo específico.
    
    Útil para:
    - Resetear series con configuración incorrecta
    - Testing y desarrollo
    - Limpieza manual
    
    Uso:
        from app.repositories.timeseries_repository import delete_series
        from app.database import redis_client
        delete_series(redis_client, user_id=6, device_id=3)
    """
    keys_to_delete = [
        f"ts:user:{user_id}:device:{device_id}:watts",
        f"ts:user:{user_id}:device:{device_id}:volts",
        f"ts:user:{user_id}:device:{device_id}:amps"
    ]
    
    deleted = 0
    for key in keys_to_delete:
        try:
            result = redis_client.delete(key)
            if result:
                deleted += 1
                logger.info(f"🗑️ Serie eliminada: {key}")
        except Exception as e:
            logger.error(f"❌ Error eliminando {key}: {e}")
    
    logger.info(f"✅ {deleted}/3 series eliminadas para user={user_id}, device={device_id}")
    return deleted