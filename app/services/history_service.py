# app/services/history_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone, timedelta
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod
from collections import defaultdict

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
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

    if period == HistoryPeriod.DAILY:
        from_dt = now_dt - timedelta(hours=24)
        bucket_duration_ms = 3600000
    elif period == HistoryPeriod.WEEKLY:
        from_dt = now_dt - timedelta(days=7)
        bucket_duration_ms = 86400000
    elif period == HistoryPeriod.MONTHLY:
        from_dt = now_dt - timedelta(days=30)
        bucket_duration_ms = 86400000
    else:
        return None

    from_ts = int(from_dt.timestamp() * 1000)

    try:
        if not redis_client.exists(watts_key):
            return None

        raw_result = redis_client.execute_command(
            'TS.RANGE', watts_key, from_ts, now_ts,
            'ALIGN', 'start', 'AGGREGATION', 'avg', bucket_duration_ms
        )

        data_points = []
        for item in raw_result:
            ts = int(item[0])
            value = float(item[1]) if item[1] is not None else 0.0
            dt_object = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            bucket_hours = (bucket_duration_ms / 1000) / 3600.0
            kwh_value = (value * bucket_hours) / 1000.0
            data_points.append({
                "timestamp": dt_object.isoformat(),
                "value": round(kwh_value, 6)
            })

        return {"period": period.value, "unit": "kWh", "data_points": data_points}
    except Exception as e:
        logger.exception(f"❌ Error: {e}")
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