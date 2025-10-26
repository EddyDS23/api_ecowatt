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

    now_dt = datetime.now(timezone.utc)
    now_ts = int(now_dt.timestamp() * 1000)

    # Configuración de periodos y buckets
    if period == HistoryPeriod.DAILY:
        from_dt = now_dt - timedelta(hours=24)
        bucket_duration_ms = 60 * 60 * 1000  # 1 hora
        expected_buckets = 24
    elif period == HistoryPeriod.WEEKLY:
        from_dt = now_dt - timedelta(days=7)
        bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
        expected_buckets = 7
    elif period == HistoryPeriod.MONTHLY:
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
        # Obtener datos agregados de Redis
        aggregated_data = redis_client.ts().range(
            watts_key,
            from_time=from_ts,
            to_time=now_ts,
            aggregation_type="avg",
            bucket_size_msec=bucket_duration_ms
        )
        
        logger.info(f"   RedisTimeSeries devolvió {len(aggregated_data)} buckets")

        # Crear un mapa de timestamp → valor para los datos que SÍ existen
        data_map = {}
        for ts, value in aggregated_data:
            # Normalizar el timestamp al inicio del bucket
            bucket_start = (ts // bucket_duration_ms) * bucket_duration_ms
            data_map[bucket_start] = float(value) if value is not None else 0.0

        # Generar TODOS los buckets esperados (incluso los vacíos)
        data_points = []
        current_ts = from_ts
        
        for i in range(expected_buckets):
            bucket_start = current_ts
            dt_object = datetime.fromtimestamp(bucket_start / 1000, tz=timezone.utc)
            
            # Buscar si hay datos para este bucket
            avg_power_watts = data_map.get(bucket_start, 0.0)
            
            # Convertir a kWh: Watts * horas / 1000
            bucket_hours = bucket_duration_ms / (1000 * 3600)
            kwh_value = (avg_power_watts * bucket_hours) / 1000.0
            
            data_points.append({
                "timestamp": dt_object,
                "value": round(kwh_value, 6)
            })
            
            current_ts += bucket_duration_ms

        logger.info(f"✅ Generados {len(data_points)} puntos completos para '{period.value}'")
        return {"period": period.value, "data_points": data_points}

    except Exception as e:
        logger.error(f"Error en _get_data_with_timeseries: {e}")
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
            dt_object = datetime.fromtimestamp(bucket_start / 1000, tz=timezone.utc)
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
        dt_object = datetime.fromtimestamp(current_ts / 1000, tz=timezone.utc)
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
    now = datetime.now(timezone.utc)
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
                    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
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