# app/services/history_service.py (VERSIÓN CORREGIDA)
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone, timedelta
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod
from collections import defaultdict

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
    """
    Devuelve data_points agrupados para el periodo pedido:
     - daily  -> últimas 24h, bucket = 1 hora  (24 puntos GARANTIZADOS)
     - weekly -> últimos 7d,  bucket = 1 día   (7 puntos GARANTIZADOS)
     - monthly-> últimos 30d, bucket = 1 día   (30 puntos GARANTIZADOS)
    
    MODO DESARROLLO: Si hay pocos datos, ajusta automáticamente el rango.
    """
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user or not getattr(user, "devices", None):
        logger.warning(f"Usuario {user_id} no encontrado o sin dispositivos")
        return None

    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        logger.warning(f"Usuario {user_id} no tiene dispositivos activos")
        return None

    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"

    now_dt = datetime.now()
    now_ts = int(now_dt.timestamp() * 1000)

    # PASO 1: Detectar el rango real de datos disponibles
    try:
        if not redis_client.exists(watts_key):
            logger.warning(f"⚠️ No existe la key en Redis: {watts_key}")
            return _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets)
        
        # Obtener primer y último timestamp
        all_data_sample = redis_client.ts().range(watts_key, "-", "+", count=1)
        if not all_data_sample:
            logger.warning(f"⚠️ La serie {watts_key} está vacía")
            return _generate_empty_response(period, now_ts - 86400000, 3600000, 24)
        
        first_ts = all_data_sample[0][0]
        data_age_hours = (now_ts - first_ts) / (1000 * 3600)
        
        logger.info(f"📊 Datos disponibles desde hace {data_age_hours:.1f} horas")
        
    except Exception as e:
        logger.error(f"Error detectando rango de datos: {e}")
        data_age_hours = 24  # Asumir 24h por defecto

    # PASO 2: Configuración adaptativa de periodos y buckets
    if period == HistoryPeriod.DAILY:
        # Si hay menos de 24h de datos, ajustar
        if data_age_hours < 24:
            # Usar el tiempo disponible, mínimo 1 hora
            hours_available = max(1, int(data_age_hours))
            from_dt = now_dt - timedelta(hours=hours_available)
            bucket_duration_ms = 60 * 60 * 1000  # 1 hora
            expected_buckets = hours_available
            logger.warning(f"⚠️ Solo hay {hours_available}h de datos, ajustando gráfica diaria")
        else:
            from_dt = now_dt - timedelta(hours=24)
            bucket_duration_ms = 60 * 60 * 1000  # 1 hora
            expected_buckets = 24
            
    elif period == HistoryPeriod.WEEKLY:
        if data_age_hours < 168:  # 7 días = 168 horas
            days_available = max(1, int(data_age_hours / 24))
            from_dt = now_dt - timedelta(days=days_available)
            bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
            expected_buckets = days_available
            logger.warning(f"⚠️ Solo hay {days_available} días de datos, ajustando gráfica semanal")
        else:
            from_dt = now_dt - timedelta(days=7)
            bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
            expected_buckets = 7
            
    elif period == HistoryPeriod.MONTHLY:
        if data_age_hours < 720:  # 30 días = 720 horas
            days_available = max(1, int(data_age_hours / 24))
            from_dt = now_dt - timedelta(days=days_available)
            bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
            expected_buckets = days_available
            logger.warning(f"⚠️ Solo hay {days_available} días de datos, ajustando gráfica mensual")
        else:
            from_dt = now_dt - timedelta(days=30)
            bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
            expected_buckets = 30
    else:
        logger.error(f"Periodo no válido: {period}")
        return None

    from_ts = int(from_dt.timestamp() * 1000)

    logger.info(f"📊 Obteniendo datos para periodo '{period.value}': {from_dt} → {now_dt}")
    logger.info(f"   Bucket size: {bucket_duration_ms}ms, Expected buckets: {expected_buckets}")

    try:
        if not redis_client.exists(watts_key):
            logger.warning(f"⚠️ No existe la key en Redis: {watts_key}")
            return _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets)

        # Verificar si tenemos RedisTimeSeries
        if hasattr(redis_client, "ts"):
            return _get_data_with_timeseries(
                redis_client, watts_key, from_ts, now_ts, 
                bucket_duration_ms, expected_buckets, period
            )
        else:
            return _get_data_with_zset_fallback(
                redis_client, watts_key, from_ts, now_ts, 
                bucket_duration_ms, expected_buckets, period
            )

    except Exception as e:
        logger.error(f"❌ Error al obtener datos históricos de {watts_key}: {e}")
        return None


def _get_data_with_timeseries(redis_client, watts_key, from_ts, now_ts, bucket_duration_ms, expected_buckets, period):
    """Obtiene datos usando RedisTimeSeries con agregación"""
    try:
        logger.info(f"🔍 Consultando RedisTimeSeries...")
        
        # Obtener datos agregados de Redis
        aggregated_data = redis_client.ts().range(
            watts_key,
            from_time=from_ts,
            to_time=now_ts,
            aggregation_type="avg",
            bucket_size_msec=bucket_duration_ms
        )
        
        logger.info(f"📥 RedisTimeSeries devolvió {len(aggregated_data)} buckets con datos")

        if len(aggregated_data) == 0:
            logger.warning(f"⚠️  No se encontraron datos en el rango especificado")
            logger.warning(f"   Esto puede significar que:")
            logger.warning(f"   1. El simulador no está enviando datos")
            logger.warning(f"   2. Los datos son demasiado antiguos")
            logger.warning(f"   3. Hay un problema de timezone")
        else:
            logger.info(f"📊 Buckets recibidos de Redis:")
            for i, (ts, value) in enumerate(aggregated_data[:5]):  # Mostrar primeros 5
                dt = datetime.fromtimestamp(ts / 1000)
                logger.info(f"   [{i}] {dt} → {value:.2f}W")
            if len(aggregated_data) > 5:
                logger.info(f"   ... y {len(aggregated_data) - 5} buckets más")

        # CRÍTICO: Crear un mapa normalizando los timestamps
        # Redis devuelve buckets alineados a la hora (ej: 20:00:00)
        # Necesitamos mapearlos correctamente
        data_map = {}
        total_watts_sum = 0
        for ts, value in aggregated_data:
            # Normalizar el timestamp del bucket al inicio de la hora/día
            normalized_ts = (ts // bucket_duration_ms) * bucket_duration_ms
            watts_value = float(value) if value is not None else 0.0
            data_map[normalized_ts] = watts_value
            total_watts_sum += watts_value
            
            dt = datetime.fromtimestamp(normalized_ts / 1000)
            logger.debug(f"   🔄 Bucket normalizado: {dt} → {watts_value:.2f}W")

        avg_watts = total_watts_sum / len(aggregated_data) if aggregated_data else 0
        logger.info(f"📈 Promedio de Watts en periodo: {avg_watts:.2f}W")

        # Generar TODOS los buckets esperados (incluyendo los vacíos)
        data_points = []
        
        # IMPORTANTE: Normalizar from_ts al inicio del bucket
        # Si from_ts = 21:22:45, normalizarlo a 21:00:00
        normalized_from_ts = (from_ts // bucket_duration_ms) * bucket_duration_ms
        current_ts = normalized_from_ts
        
        logger.info(f"🔨 Generando {expected_buckets} data points...")
        logger.info(f"   Inicio normalizado: {datetime.fromtimestamp(normalized_from_ts / 1000)}")
        
        total_kwh = 0
        points_with_data = 0
        
        for i in range(expected_buckets):
            bucket_start = current_ts
            dt_object = datetime.fromtimestamp(bucket_start / 1000)
            
            # Buscar si hay datos para este bucket normalizado
            avg_power_watts = data_map.get(bucket_start, 0.0)
            
            # Convertir a kWh: Watts * horas / 1000
            bucket_hours = bucket_duration_ms / (1000 * 3600)
            kwh_value = (avg_power_watts * bucket_hours) / 1000.0
            
            data_points.append({
                "timestamp": dt_object,
                "value": round(kwh_value, 6)
            })
            
            if kwh_value > 0:
                points_with_data += 1
                total_kwh += kwh_value
                logger.info(f"   ✅ Bucket [{i:2d}] {dt_object.strftime('%Y-%m-%d %H:%M')} → {avg_power_watts:7.2f}W = {kwh_value:.6f} kWh")
            else:
                logger.debug(f"   ⚪ Bucket [{i:2d}] {dt_object.strftime('%Y-%m-%d %H:%M')} → Sin datos (0 kWh)")
            
            current_ts += bucket_duration_ms

        logger.info(f"📊 ============================================")
        logger.info(f"📊 RESUMEN DE RESULTADOS")
        logger.info(f"📊 ============================================")
        logger.info(f"✅ Total de puntos generados: {len(data_points)}")
        logger.info(f"📈 Puntos con datos: {points_with_data}")
        logger.info(f"📉 Puntos vacíos: {len(data_points) - points_with_data}")
        logger.info(f"⚡ Total kWh en periodo: {total_kwh:.4f} kWh")
        logger.info(f"⚡ Promedio por punto: {total_kwh/points_with_data:.4f} kWh" if points_with_data > 0 else "⚡ Promedio: N/A")
        logger.info(f"📊 ============================================")
        
        return {"period": period.value, "data_points": data_points}

    except Exception as e:
        logger.error(f"❌ Error en _get_data_with_timeseries: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def _get_data_with_zset_fallback(redis_client, watts_key, from_ts, now_ts, bucket_duration_ms, expected_buckets, period):
    """Fallback usando ZSET si no hay RedisTimeSeries"""
    try:
        raw = redis_client.zrangebyscore(watts_key, from_ts, now_ts, withscores=True)
        logger.info(f"   ZSET devolvió {len(raw)} puntos raw")

        # Crear buckets vacíos
        buckets = {}
        current_ts = from_ts
        for i in range(expected_buckets):
            buckets[current_ts] = {"sum": 0.0, "count": 0}
            current_ts += bucket_duration_ms

        # Llenar buckets con datos reales
        for val, score in raw:
            try:
                v = float(val)
            except Exception:
                try:
                    import json
                    v = float(json.loads(val).get("watts", 0))
                except Exception:
                    v = 0.0
            
            # Encontrar el bucket correspondiente
            bucket_start = ((int(score) - from_ts) // bucket_duration_ms) * bucket_duration_ms + from_ts
            if bucket_start in buckets:
                buckets[bucket_start]["sum"] += v
                buckets[bucket_start]["count"] += 1

        # Generar data_points con todos los buckets
        data_points = []
        for bucket_start in sorted(buckets.keys()):
            dt_object = datetime.fromtimestamp(bucket_start / 1000)
            agg = buckets[bucket_start]
            
            if agg["count"] == 0:
                kwh_value = 0.0
            else:
                avg_power_watts = agg["sum"] / agg["count"]
                bucket_hours = bucket_duration_ms / (1000 * 3600)
                kwh_value = (avg_power_watts * bucket_hours) / 1000.0
            
            data_points.append({
                "timestamp": dt_object,
                "value": round(kwh_value, 6)
            })

        logger.info(f"✅ Generados {len(data_points)} puntos con ZSET para '{period.value}'")
        return {"period": period.value, "data_points": data_points}

    except Exception as e:
        logger.error(f"Error en _get_data_with_zset_fallback: {e}")
        raise


def _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets):
    """Genera una respuesta con buckets vacíos cuando no hay datos"""
    data_points = []
    current_ts = from_ts
    
    for i in range(expected_buckets):
        dt_object = datetime.fromtimestamp(current_ts / 1000)
        data_points.append({
            "timestamp": dt_object,
            "value": 0.0
        })
        current_ts += bucket_duration_ms
    
    logger.info(f"⚠️ Generados {expected_buckets} puntos vacíos (sin datos en Redis)")
    return {"period": period.value, "data_points": data_points}


def get_last_7_days_data(db, redis_client, user_id: int):
    """
    Recupera datos de los últimos 7 días desde RedisTimeSeries y devuelve
    data_points con timestamp y value en kWh.
    GARANTIZA 7 PUNTOS COMPLETOS.
    
    Formato de respuesta:
    {
        "unit": "kWh",
        "data_points": [
            {"timestamp": "2025-10-19T00:00:00Z", "value": 0.5},
            {"timestamp": "2025-10-20T00:00:00Z", "value": 0.8},
            ...
        ]
    }
    """
    now = datetime.now()
    # Calcular inicio hace exactamente 7 días (a medianoche)
    start_time = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)

    logger.info(f"📊 get_last_7_days_data para user {user_id}")
    logger.info(f"   Rango: {start_time} → {now}")

    # Buscar todas las keys de dispositivos del usuario
    keys = redis_client.keys(f"ts:user:{user_id}:device:*:watts")
    if not keys:
        logger.warning(f"⚠️ No se encontraron keys para user {user_id}")
        return _generate_empty_7_days_response(start_time)

    logger.info(f"   Encontradas {len(keys)} keys de dispositivos")

    # Diccionario para agrupar TODAS las mediciones por fecha
    grouped_measurements = defaultdict(list)

    # Procesar cada dispositivo
    for key in keys:
        key_str = key.decode() if isinstance(key, bytes) else key
        logger.info(f"   Procesando key: {key_str}")

        try:
            # Obtener TODOS los puntos de watts en el rango
            watts_data = redis_client.ts().range(key_str, start_ts, end_ts)
            logger.info(f"      Watts: {len(watts_data)} puntos")

            # Agrupar TODAS las mediciones por fecha
            for ts, value in watts_data:
                try:
                    # Convertir timestamp a fecha (sin hora)
                    dt = datetime.fromtimestamp(ts / 1000)
                    date_str = dt.strftime("%Y-%m-%d")
                    
                    # Guardar timestamp y valor
                    grouped_measurements[date_str].append({
                        "timestamp": ts,
                        "watts": float(value)
                    })
                except Exception as e:
                    logger.error(f"Error procesando punto: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error procesando key {key_str}: {e}")
            continue

    # Log de datos agrupados
    logger.info(f"   Datos agrupados por fecha: {list(grouped_measurements.keys())}")
    for date, measurements in grouped_measurements.items():
        logger.info(f"      {date}: {len(measurements)} mediciones")

    # Generar data_points para los últimos 7 días
    data_points = []
    
    for i in range(7):
        # Fecha del día
        date_obj = start_time + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        
        # Timestamp ISO 8601 a medianoche de ese día
        timestamp_iso = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        
        # Obtener mediciones de ese día
        day_measurements = grouped_measurements.get(date_str, [])
        
        if not day_measurements:
            # Día sin datos
            data_points.append({
                "timestamp": timestamp_iso,
                "value": 0.0
            })
            logger.info(f"      {date_str}: Sin datos → 0.0 kWh")
        else:
            # Calcular kWh del día usando integración trapezoidal
            # Ordenar por timestamp
            day_measurements.sort(key=lambda x: x["timestamp"])
            
            total_watt_seconds = 0.0
            for j in range(1, len(day_measurements)):
                t0 = day_measurements[j-1]["timestamp"]
                t1 = day_measurements[j]["timestamp"]
                w0 = day_measurements[j-1]["watts"]
                w1 = day_measurements[j]["watts"]
                
                # Tiempo transcurrido en segundos
                dt_seconds = (t1 - t0) / 1000.0
                
                # Potencia promedio en el intervalo
                avg_watts = (w0 + w1) / 2.0
                
                # Energía = Potencia × Tiempo
                total_watt_seconds += avg_watts * dt_seconds
            
            # Convertir Watt-segundos a kWh
            kwh_value = total_watt_seconds / 3_600_000.0  # (W·s) / (1000 W/kW × 3600 s/h)
            
            data_points.append({
                "timestamp": timestamp_iso,
                "value": round(kwh_value, 4)
            })
            logger.info(f"      {date_str}: {len(day_measurements)} mediciones → {kwh_value:.4f} kWh")

    logger.info(f"✅ get_last_7_days_data: Generados {len(data_points)} data_points")
    
    return {
        "unit": "kWh",
        "data_points": data_points
    }


def _generate_empty_7_days_response(start_time):
    """Genera respuesta vacía con 7 días de ceros en formato data_points"""
    data_points = []
    
    for i in range(7):
        date_obj = start_time + timedelta(days=i)
        timestamp_iso = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        
        data_points.append({
            "timestamp": timestamp_iso,
            "value": 0.0
        })
    
    logger.info(f"⚠️ Generados 7 data_points vacíos (sin datos)")
    return {
        "unit": "kWh",
        "data_points": data_points
    }