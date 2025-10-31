# app/services/history_service.py
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
     - daily  -> últimos 24h, bucket = 1 hora  (24 puntos)
     - weekly -> últimos 7d,  bucket = 1 día   (7  puntos)
     - monthly-> últimos 30d, bucket = 1 día   (30 puntos)
    Soporta RedisTimeSeries (recomendado). Si no está, intenta leer desde ZSET fallback.
    """
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user or not getattr(user, "devices", None):
        return None

    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        return None

    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"

    now_dt = datetime.now(timezone.utc)
    now_ts = int(now_dt.timestamp() * 1000)

    # Configuración de buckets
    if period == HistoryPeriod.DAILY:
        from_dt = now_dt - timedelta(hours=24)
        bucket_duration_ms = 60 * 60 * 1000  # 1 hora
    elif period == HistoryPeriod.WEEKLY:
        from_dt = now_dt - timedelta(days=7)
        bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
    elif period == HistoryPeriod.MONTHLY:
        from_dt = now_dt - timedelta(days=30)
        bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
    else:
        return None

    from_ts = int(from_dt.timestamp() * 1000)

    try:
        # Intentamos usar RedisTimeSeries (módulo TS)
        if hasattr(redis_client, "ts"):
            # ts().range with aggregation
            aggregated_data = redis_client.ts().range(
                watts_key,
                from_time=from_ts,
                to_time=now_ts,
                aggregation_type="avg",
                bucket_size_msec=bucket_duration_ms
            )
            # aggregated_data is list of [timestamp, value]
            data_points = []
            for ts, value in aggregated_data:
                dt_object = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    
                # Manejar valores None (buckets sin datos)
                if value is None:
                    avg_power_watts = 0.0
                else:
                    avg_power_watts = float(value)
    
                # Convertir W promedio a kWh basado en duración del bucket
                bucket_hours = (bucket_duration_ms / 1000) / 3600.0
                kwh_value = (avg_power_watts * bucket_hours) / 1000.0
    
                data_points.append({
                    "timestamp": dt_object.isoformat(),  # ✅ Formato ISO8601 para frontend
                    "value": round(kwh_value, 6)
                })

            # Si quieres garantizar N puntos fijos (por ejemplo 7 días), construir buckets con ceros
            # y mapear los resultados en ellos. Aquí devolvemos los buckets realmente devueltos por TS.
            return {"period": period.value, "data_points": data_points}

        else:
            # Fallback: si no tienes RedisTimeSeries, asumimos que guardaste con ZADD (score=timestamp_ms)
            raw = redis_client.zrangebyscore(watts_key, from_ts, now_ts, withscores=True)
            # raw = [(value, score_ms), ...]
            # convertimos y agrupamos por bucket manually
            buckets = {}
            # crear buckets vacíos
            n_buckets = int((now_ts - from_ts) / bucket_duration_ms) + 1
            for i in range(n_buckets):
                bucket_start = from_ts + i * bucket_duration_ms
                buckets[bucket_start] = {"sum": 0.0, "count": 0}

            for val, score in raw:
                # score puede venir en float/int; val puede estar serializado
                try:
                    v = float(val)
                except Exception:
                    # si el valor es JSON con {"watts":...}
                    try:
                        import json
                        v = float(json.loads(val).get("watts", 0))
                    except Exception:
                        v = 0.0
                # ubicar bucket
                relative = int((score - from_ts) // bucket_duration_ms)
                bucket_start = from_ts + relative * bucket_duration_ms
                if bucket_start not in buckets:
                    buckets[bucket_start] = {"sum": 0.0, "count": 0}
                buckets[bucket_start]["sum"] += v
                buckets[bucket_start]["count"] += 1

            data_points = []
            for bucket_start, agg in sorted(buckets.items()):
                ts = bucket_start
                if agg["count"] == 0:
                    data_points.append({"timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc), "value": 0.0})
                else:
                    avg_power_watts = agg["sum"] / agg["count"]
                    bucket_hours = (bucket_duration_ms / 1000) / 3600.0
                    kwh_value = (avg_power_watts * bucket_hours) / 1000.0
                    data_points.append({"timestamp": datetime.fromtimestamp(ts / 1000, tz=timezone.utc), "value": round(kwh_value, 6)})

            return {"period": period.value, "data_points": data_points}

    except Exception as e:
        logger.error(f"Error al obtener datos históricos de Redis para {watts_key}: {e}")
        return None


def get_last_7_days_data(db, redis_client, user_id: int):
    """
    Recupera datos de los últimos 7 días desde RedisTimeSeries y devuelve
    promedios diarios listos para graficar (labels, watts, volts, amps).
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=7)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)

    # Buscar series del usuario (solo watts, luego derivamos volts y amps)
    keys = redis_client.keys(f"ts:user:{user_id}:device:*:watts")
    if not keys:
        return None

    # Diccionario global por fecha
    grouped = defaultdict(lambda: {"watts": [], "volts": [], "amps": []})

    for key in keys:
        key = key.decode() if isinstance(key, bytes) else key
        device_id = key.split(":")[5]

        watts_data = redis_client.ts().range(key, start_ts, end_ts)
        volts_data = redis_client.ts().range(key.replace("watts", "volts"), start_ts, end_ts)
        amps_data  = redis_client.ts().range(key.replace("watts", "amps"),  start_ts, end_ts)

        # Agrupar por fecha
        for ts, value in watts_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["watts"].append(value)
        for ts, value in volts_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["volts"].append(value)
        for ts, value in amps_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["amps"].append(value)

    # Calcular promedios diarios
    sorted_dates = sorted(grouped.keys())
    labels, watts_list, volts_list, amps_list = [], [], [], []

    for date in sorted_dates:
        labels.append(date)
        measures = grouped[date]
        watts_list.append(sum(measures["watts"]) / len(measures["watts"]) if measures["watts"] else 0)
        volts_list.append(sum(measures["volts"]) / len(measures["volts"]) if measures["volts"] else 0)
        amps_list.append(sum(measures["amps"]) / len(measures["amps"]) if measures["amps"] else 0)
    
    labels_iso = [
    datetime.strptime(date, "%Y-%m-%d")
    .replace(tzinfo=timezone.utc)
    .isoformat() 
    for date in labels
]

    return {
        "labels": labels_iso,
        "watts": watts_list,
        "volts": volts_list,
        "amps": amps_list
    }