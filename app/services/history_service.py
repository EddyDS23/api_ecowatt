# app/services/history_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone, timedelta
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod
from collections import defaultdict
import json

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
    """
    Devuelve data_points agrupados para el periodo pedido:
     - daily  -> últimas 24h, bucket = 1 hora
     - weekly -> últimos 7d,  bucket = 1 día
     - monthly-> últimos 30d, bucket = 1 día
    Ajusta automáticamente si hay pocos datos.
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

    # Detectar rango real de datos
    try:
        if not redis_client.exists(watts_key):
            logger.warning(f"⚠️ No existe la key en Redis: {watts_key}")
            return _generate_empty_response(period, now_ts - 3600000, 3600000, 1)
        
        all_data_sample = redis_client.ts().range(watts_key, "-", "+", count=1)
        if not all_data_sample:
            logger.warning(f"⚠️ La serie {watts_key} está vacía")
            return _generate_empty_response(period, now_ts - 3600000, 3600000, 1)
        
        first_ts = all_data_sample[0][0]
        data_age_hours = (now_ts - first_ts) / (1000 * 3600)
        logger.info(f"📊 Datos disponibles desde hace {data_age_hours:.1f} horas")
    except Exception as e:
        logger.error(f"Error detectando rango de datos: {e}")
        data_age_hours = 24
        first_ts = now_ts - 24 * 3600 * 1000

    # Configuración de periodos
    if period == HistoryPeriod.DAILY:
        hours_available = min(24, max(1, int(data_age_hours)))
        from_dt = now_dt - timedelta(hours=hours_available)
        bucket_duration_ms = 60 * 60 * 1000
        expected_buckets = hours_available
        if hours_available < 24:
            logger.warning(f"⚠️ Solo hay {hours_available}h de datos, ajustando gráfica diaria")
    elif period == HistoryPeriod.WEEKLY:
        days_available = min(7, max(1, int(data_age_hours / 24)))
        from_dt = now_dt - timedelta(days=days_available)
        bucket_duration_ms = 24 * 60 * 60 * 1000
        expected_buckets = days_available
        if days_available < 7:
            logger.warning(f"⚠️ Solo hay {days_available} días de datos, ajustando gráfica semanal")
    elif period == HistoryPeriod.MONTHLY:
        days_available = min(30, max(1, int(data_age_hours / 24)))
        from_dt = now_dt - timedelta(days=days_available)
        bucket_duration_ms = 24 * 60 * 60 * 1000
        expected_buckets = days_available
        if days_available < 30:
            logger.warning(f"⚠️ Solo hay {days_available} días de datos, ajustando gráfica mensual")
    else:
        logger.error(f"Periodo no válido: {period}")
        return None

    from_ts = int(from_dt.timestamp() * 1000)
    logger.info(f"📊 Obteniendo datos para periodo '{period.value}': {from_dt} → {now_dt}")
    logger.info(f"   Bucket size: {bucket_duration_ms}ms, Expected buckets: {expected_buckets}")

    try:
        if hasattr(redis_client, "ts"):
            return _get_data_with_timeseries(
                redis_client, watts_key, from_ts, now_ts,
                bucket_duration_ms, expected_buckets, period, first_ts
            )
        else:
            return _get_data_with_zset_fallback(
                redis_client, watts_key, from_ts, now_ts,
                bucket_duration_ms, expected_buckets, period
            )
    except Exception as e:
        logger.error(f"❌ Error al obtener datos históricos de {watts_key}: {e}")
        return None


def _get_data_with_timeseries(redis_client, watts_key, from_ts, now_ts, bucket_duration_ms, expected_buckets, period, first_ts):
    """Obtiene datos usando RedisTimeSeries con agregación, corrigiendo el desfase horario"""
    try:
        logger.info(f"🔍 Consultando RedisTimeSeries...")
        aggregated_data = redis_client.ts().range(
            watts_key,
            from_time=from_ts,
            to_time=now_ts,
            aggregation_type="avg",
            bucket_size_msec=bucket_duration_ms
        )

        logger.info(f"📥 RedisTimeSeries devolvió {len(aggregated_data)} buckets con datos")
        if aggregated_data:
            for i, (ts, value) in enumerate(aggregated_data[:5]):
                dt = datetime.utcfromtimestamp(ts / 1000)
                logger.info(f"   [{i}] {dt} → {value:.2f}W")
            if len(aggregated_data) > 5:
                logger.info(f"   ... y {len(aggregated_data) - 5} buckets más")

        # Crear mapa de buckets normalizados (timestamp inicio bucket)
        data_map = {}
        for ts, value in aggregated_data:
            normalized_ts = (ts // bucket_duration_ms) * bucket_duration_ms
            data_map[normalized_ts] = float(value) if value is not None else 0.0

        # Normalizar inicio desde primer bucket real (no desde 'from_ts')
        normalized_from_ts = (first_ts // bucket_duration_ms) * bucket_duration_ms
        current_ts = normalized_from_ts

        data_points = []
        total_kwh = 0
        points_with_data = 0

        logger.info(f"🔨 Generando {expected_buckets} data points...")
        logger.info(f"   Inicio normalizado: {datetime.utcfromtimestamp(normalized_from_ts / 1000)}")

        for i in range(expected_buckets):
            dt_object = datetime.utcfromtimestamp(current_ts / 1000)
            avg_power_watts = data_map.get(current_ts, 0.0)
            bucket_hours = bucket_duration_ms / (1000 * 3600)
            kwh_value = (avg_power_watts * bucket_hours) / 1000.0

            data_points.append({
                "timestamp": dt_object,
                "value": round(kwh_value, 6)
            })

            if kwh_value > 0:
                points_with_data += 1
                total_kwh += kwh_value
                logger.info(f"   ✅ Bucket [{i:2d}] {dt_object.strftime('%Y-%m-%d %H:%M')} → {avg_power_watts:.2f}W = {kwh_value:.6f} kWh")
            else:
                logger.debug(f"   ⚪ Bucket [{i:2d}] {dt_object.strftime('%Y-%m-%d %H:%M')} → Sin datos (0 kWh)")

            current_ts += bucket_duration_ms

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
    raw = redis_client.zrangebyscore(watts_key, from_ts, now_ts, withscores=True)
    logger.info(f"   ZSET devolvió {len(raw)} puntos raw")

    buckets = {}
    current_ts = from_ts
    for _ in range(expected_buckets):
        buckets[current_ts] = {"sum": 0.0, "count": 0}
        current_ts += bucket_duration_ms

    for val, score in raw:
        try:
            v = float(val)
        except Exception:
            try:
                v = float(json.loads(val).get("watts", 0))
            except Exception:
                v = 0.0
        bucket_start = ((int(score) - from_ts) // bucket_duration_ms) * bucket_duration_ms + from_ts
        if bucket_start in buckets:
            buckets[bucket_start]["sum"] += v
            buckets[bucket_start]["count"] += 1

    data_points = []
    for bucket_start in sorted(buckets.keys()):
        dt_object = datetime.utcfromtimestamp(bucket_start / 1000)
        agg = buckets[bucket_start]
        if agg["count"] == 0:
            kwh_value = 0.0
        else:
            avg_power_watts = agg["sum"] / agg["count"]
            bucket_hours = bucket_duration_ms / (1000 * 3600)
            kwh_value = (avg_power_watts * bucket_hours) / 1000.0
        data_points.append({"timestamp": dt_object, "value": round(kwh_value, 6)})

    logger.info(f"✅ Generados {len(data_points)} puntos con ZSET para '{period.value}'")
    return {"period": period.value, "data_points": data_points}


def _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets):
    data_points = []
    current_ts = from_ts
    for _ in range(expected_buckets):
        dt_object = datetime.utcfromtimestamp(current_ts / 1000)
        data_points.append({"timestamp": dt_object, "value": 0.0})
        current_ts += bucket_duration_ms
    logger.info(f"⚠️ Generados {expected_buckets} puntos vacíos (sin datos en Redis)")
    return {"period": period.value, "data_points": data_points}


def get_last_7_days_data(db, redis_client, user_id: int):
    """Obtiene data_points diarios de los últimos 7 días con kWh"""
    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)

    logger.info(f"📊 get_last_7_days_data para user {user_id} → {start_time} - {now}")
    keys = redis_client.keys(f"ts:user:{user_id}:device:*:watts")
    if not keys:
        return _generate_empty_7_days_response(start_time)

    grouped_measurements = defaultdict(list)
    for key in keys:
        key_str = key.decode() if isinstance(key, bytes) else key
        try:
            watts_data = redis_client.ts().range(key_str, start_ts, end_ts)
            for ts, value in watts_data:
                dt = datetime.utcfromtimestamp(ts / 1000)
                date_str = dt.strftime("%Y-%m-%d")
                grouped_measurements[date_str].append({"timestamp": ts, "watts": float(value)})
        except Exception as e:
            logger.error(f"Error procesando key {key_str}: {e}")
            continue

    data_points = []
    for i in range(7):
        date_obj = start_time + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        timestamp_iso = date_obj.isoformat() + "Z"
        day_measurements = grouped_measurements.get(date_str, [])

        if not day_measurements:
            data_points.append({"timestamp": timestamp_iso, "value": 0.0})
        else:
            day_measurements.sort(key=lambda x: x["timestamp"])
            total_watt_seconds = 0.0
            for j in range(1, len(day_measurements)):
                t0 = day_measurements[j-1]["timestamp"]
                t1 = day_measurements[j]["timestamp"]
                w0 = day_measurements[j-1]["watts"]
                w1 = day_measurements[j]["watts"]
                dt_seconds = (t1 - t0) / 1000.0
                avg_watts = (w0 + w1) / 2.0
                total_watt_seconds += avg_watts * dt_seconds
            kwh_value = total_watt_seconds / 3_600_000.0
            data_points.append({"timestamp": timestamp_iso, "value": round(kwh_value, 4)})

    return {"unit": "kWh", "data_points": data_points}


def _generate_empty_7_days_response(start_time):
    data_points = []
    for i in range(7):
        date_obj = start_time + timedelta(days=i)
        timestamp_iso = date_obj.isoformat() + "Z"
        data_points.append({"timestamp": timestamp_iso, "value": 0.0})
    return {"unit": "kWh", "data_points": data_points}
