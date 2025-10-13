from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user or not user.devices:
        return None

    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        return None

    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
    now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)

    aggregator = "avg"
    bucket_duration_ms = 0
    from_ts = 0

    if period == HistoryPeriod.DAILY:
        from_ts = now_ts - (24 * 60 * 60 * 1000)
        bucket_duration_ms = 60 * 60 * 1000  # 1 hora
    elif period == HistoryPeriod.WEEKLY:
        from_ts = now_ts - (7 * 24 * 60 * 60 * 1000)
        bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día
    elif period == HistoryPeriod.MONTHLY:
        from_ts = now_ts - (30 * 24 * 60 * 60 * 1000)
        bucket_duration_ms = 24 * 60 * 60 * 1000  # 1 día

    try:
        if not redis_client.exists(watts_key):
            logger.warning(f"Serie {watts_key} no encontrada en Redis")
            return {"period": period.value, "data_points": []}

        aggregated_data = redis_client.ts().range(
            watts_key,
            from_time=from_ts,
            to_time=now_ts,
            aggregation_type=aggregator,
            bucket_size_msec=bucket_duration_ms,
        )

        data_points = []
        for ts, value in aggregated_data:
            if value is None:
                continue

            dt_object = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            avg_power_watts = float(value)

            # Conversión precisa: W → kWh
            kwh_value = avg_power_watts * (bucket_duration_ms / 3_600_000_000)
            data_points.append({"timestamp": dt_object, "value": round(kwh_value, 4)})

        return {"period": period.value, "data_points": data_points}

    except Exception as e:
        logger.error(f"Error al obtener datos históricos de Redis para {watts_key}: {e}")
        return None
