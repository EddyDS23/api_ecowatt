# app/repositories/timeseries_repository.py (VERSIÓN SEGURA - SIN TS.ALTER)

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
        
        🔥 REGLAS CRÍTICAS:
        1. Si la serie NO existe → Se crea con configuración correcta
        2. Si la serie existe con config incorrecta → Solo ALERTA (NO modifica)
        3. Si la serie existe con config correcta → La agrega al cache
        
        ⚠️ NO usa TS.ALTER para evitar reseteo de chunks y pérdida de datos.
        """
        
        # Si ya verificamos esta serie en esta sesión, saltamos
        if key in _GLOBAL_CREATED_SERIES:
            return
        
        try:
            # Verificar si la serie existe en Redis
            info = self.redis.ts().info(key)
            
            # Serie existe, validar configuración
            current_retention = info.get('retentionTime', 0)
            current_dup_policy = info.get('duplicatePolicy')
            
            # Verificar si la configuración es correcta
            config_is_correct = (
                current_retention == RETENTION_MS and 
                current_dup_policy == 'last'
            )
            
            if not config_is_correct:
                # 🚨 ALERTA: Configuración incorrecta detectada
                logger.error(
                    f"❌ CONFIGURACIÓN INCORRECTA EN SERIE EXISTENTE: {key}\n"
                    f"   ┌─ Configuración Actual:\n"
                    f"   │  • Retention: {current_retention}ms ({current_retention / 86400000:.1f} días)\n"
                    f"   │  • Duplicate Policy: {current_dup_policy}\n"
                    f"   ├─ Configuración Esperada:\n"
                    f"   │  • Retention: {RETENTION_MS}ms (30 días)\n"
                    f"   │  • Duplicate Policy: last\n"
                    f"   └─ ACCIÓN REQUERIDA:\n"
                    f"      1. Detener el backend: sudo systemctl stop ecowatt\n"
                    f"      2. Eliminar la serie: sudo docker exec ecowatt-redis redis-cli DEL {key}\n"
                    f"      3. Reiniciar backend: sudo systemctl start ecowatt\n"
                    f"      4. La serie se recreará automáticamente con configuración correcta"
                )
                # ⚠️ IMPORTANTE: NO intentamos corregir con TS.ALTER
                # Razón: TS.ALTER puede causar pérdida de datos y reseteo de chunks
            else:
                # ✅ Configuración correcta
                logger.debug(f"✅ Serie verificada con configuración correcta: {key}")
            
            # Agregar al cache para no verificar de nuevo en esta sesión
            _GLOBAL_CREATED_SERIES.add(key)
            return
            
        except Exception as check_error:
            # Serie NO existe, la creamos con configuración correcta
            try:
                logger.info(f"📝 Creando nueva serie: {key}")
                
                # 🔥 ORDEN CRÍTICO DE PARÁMETROS (no cambiar):
                # TS.CREATE key RETENTION ms DUPLICATE_POLICY policy LABELS ...
                self.redis.execute_command(
                    'TS.CREATE', key,
                    'RETENTION', str(RETENTION_MS),          # ✅ PRIMERO
                    'DUPLICATE_POLICY', 'LAST',              # ✅ SEGUNDO
                    'LABELS',                                # ✅ TERCERO
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
                    f"✅ Serie creada exitosamente: {key}\n"
                    f"   • RETENTION: {verify_retention}ms ({verify_retention / 86400000:.1f} días)\n"
                    f"   • DUPLICATE_POLICY: {verify_dup_policy}"
                )
                
                # Validar que se creó con la configuración esperada
                if verify_retention != RETENTION_MS:
                    logger.error(
                        f"❌ ADVERTENCIA CRÍTICA: Serie creada con retention incorrecto\n"
                        f"   • Esperado: {RETENTION_MS}ms\n"
                        f"   • Obtenido: {verify_retention}ms\n"
                        f"   • Posible causa: Orden incorrecto de parámetros en TS.CREATE"
                    )
                
                if verify_dup_policy != 'last':
                    logger.error(
                        f"❌ ADVERTENCIA CRÍTICA: Serie creada con duplicate policy incorrecto\n"
                        f"   • Esperado: last\n"
                        f"   • Obtenido: {verify_dup_policy}"
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
        
        Optimización: Usa TS.MADD para insertar 3 valores en una sola operación.
        """
        # Generar timestamp UTC actual
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Construir nombres de las series
        key_watts = f"ts:user:{user_id}:device:{device_id}:watts"
        key_volts = f"ts:user:{user_id}:device:{device_id}:volts"
        key_amps  = f"ts:user:{user_id}:device:{device_id}:amps"

        try:
            # Asegurar que las series existan con la configuración correcta
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

            # Insertar datos usando TS.MADD (más eficiente que 3 TS.ADD)
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


def clear_series_cache():
    """
    Limpia el cache de series verificadas.
    
    Útil cuando:
    - Se reinicia Redis y necesitas forzar re-verificación
    - Se eliminan series manualmente y quieres que se recreen
    - Debugging de problemas de configuración
    
    Uso:
        from app.repositories.timeseries_repository import clear_series_cache
        clear_series_cache()
    """
    global _GLOBAL_CREATED_SERIES
    _GLOBAL_CREATED_SERIES.clear()
    logger.info("🔄 Cache de series limpiado")