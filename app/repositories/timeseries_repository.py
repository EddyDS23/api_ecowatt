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
        
        🔥 CAMBIO CRÍTICO:
        - NO usa cache local (eliminado _GLOBAL_CREATED_SERIES)
        - SIEMPRE verifica en Redis directamente
        - Compatible con múltiples workers de Gunicorn/Uvicorn
        
        ⚠️ Cada llamada hace TS.INFO, pero Redis es tan rápido (~1ms)
           que el overhead es insignificante vs la robustez ganada.
        """
        
        try:
            # ✅ SIEMPRE verificar en Redis (fuente de verdad)
            info = self.redis.ts().info(key)
            
            # ✅ Serie existe, validar configuración
            # FIX: info es un objeto TSInfo, no un dict
            # Acceder a propiedades directamente
            current_retention = info.retention_msecs
            current_dup_policy = info.duplicate_policy
            
            # Verificar configuración correcta
            # Redis puede devolver bytes (b'last') o string ('last') según versión/configuración
            config_is_correct = (
                current_retention == RETENTION_MS and 
                current_dup_policy in (b'last', 'last')
            )
            
            if not config_is_correct:
                # Convertir a string para mostrar correctamente
                dup_policy_str = current_dup_policy.decode() if isinstance(current_dup_policy, bytes) else current_dup_policy
                
                logger.error(
                    f"❌ CONFIGURACIÓN INCORRECTA: {key}\n"
                    f"   • Retention actual: {current_retention}ms (esperado: {RETENTION_MS}ms)\n"
                    f"   • Duplicate Policy: {dup_policy_str} (esperado: last)\n"
                    f"   • ACCIÓN: Eliminar y recrear manualmente:\n"
                    f"     sudo docker exec ecowatt-redis redis-cli DEL {key}"
                )
            else:
                logger.debug(f"✅ Serie verificada: {key}")
            
            return  # Serie existe, no hacer nada más
            
        except Exception as check_error:
            # Serie NO existe o hubo error al verificar
            error_msg = str(check_error).lower()
            
            # Si el error NO es "no existe", loggearlo
            if "key does not exist" not in error_msg and "no such key" not in error_msg:
                logger.debug(f"ℹ️ Serie {key} no existe, creando...")
            
            # Intentar crear la serie
            try:
                logger.info(f"📝 Creando nueva serie: {key}")
                
                # 🔥 ORDEN CRÍTICO DE PARÁMETROS:
                # TS.CREATE key RETENTION ms DUPLICATE_POLICY policy LABELS ...
                self.redis.execute_command(
                    'TS.CREATE', key,
                    'RETENTION', str(RETENTION_MS),
                    'DUPLICATE_POLICY', 'LAST',
                    'LABELS',
                    'user_id', str(labels.get('user_id', '')),
                    'device_id', str(labels.get('device_id', '')),
                    'type', str(labels.get('type', ''))
                )
                
                # ✅ Verificar que se creó correctamente
                verify_info = self.redis.ts().info(key)
                verify_retention = verify_info.retention_msecs
                verify_dup_policy = verify_info.duplicate_policy
                
                logger.info(
                    f"✅ Serie creada: {key}\n"
                    f"   • RETENTION: {verify_retention}ms ({verify_retention / 86400000:.1f} días)\n"
                    f"   • DUPLICATE_POLICY: {verify_dup_policy.decode() if isinstance(verify_dup_policy, bytes) else verify_dup_policy}"
                )
                
                # Validar configuración
                if verify_retention != RETENTION_MS:
                    logger.error(
                        f"❌ ADVERTENCIA: Serie creada con retention incorrecto\n"
                        f"   • Esperado: {RETENTION_MS}ms\n"
                        f"   • Obtenido: {verify_retention}ms"
                    )
                
                # Convertir a string para comparar
                verify_dup_str = verify_dup_policy.decode() if isinstance(verify_dup_policy, bytes) else verify_dup_policy
                if verify_dup_str != 'last':
                    logger.error(
                        f"❌ ADVERTENCIA: Duplicate policy incorrecto\n"
                        f"   • Esperado: last\n"
                        f"   • Obtenido: {verify_dup_str}"
                    )
                
            except Exception as create_error:
                create_error_msg = str(create_error).lower()
                
                # Si otro worker la creó justo ahora (race condition), está bien
                if "already exists" in create_error_msg or "tsdb: key already exists" in create_error_msg:
                    logger.debug(f"✅ Serie ya existe (creada por otro worker): {key}")
                else:
                    # Error real al crear
                    logger.error(f"❌ Error creando serie {key}: {create_error}")
                    raise  # Re-lanzar para que el caller lo maneje

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