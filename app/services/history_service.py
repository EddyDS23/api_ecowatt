# app/services/history_service.py (SOLUCIÓN COMPLETA)
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone, timedelta
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod
from collections import defaultdict

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
    """
    Obtiene datos históricos agregados por periodo.
    
    ✅ FIXES:
    1. Usa timestamps UTC correctamente
    2. Calcula bucket_duration_ms correcto
    3. Maneja ALIGN correctamente
    4. Convierte watts promedio a kWh correctamente
    """
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user or not getattr(user, "devices", None):
        logger.error(f"Usuario {user_id} no encontrado o sin dispositivos")
        return None

    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        logger.error(f"Usuario {user_id} no tiene dispositivos activos")
        return None

    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
    
    # ✅ FIX: Usar UTC correctamente
    now_dt = datetime.now(timezone.utc)
    now_ts = int(now_dt.timestamp() * 1000)

    # ✅ FIX: Configurar periodos correctamente
    if period == HistoryPeriod.DAILY:
        from_dt = now_dt - timedelta(hours=24)
        bucket_duration_ms = 3600000  # 1 hora en ms
        expected_buckets = 24
    elif period == HistoryPeriod.WEEKLY:
        from_dt = now_dt - timedelta(days=7)
        bucket_duration_ms = 86400000  # 1 día en ms
        expected_buckets = 7
    elif period == HistoryPeriod.MONTHLY:
        from_dt = now_dt - timedelta(days=30)
        bucket_duration_ms = 86400000  # 1 día en ms
        expected_buckets = 30
    else:
        logger.error(f"Periodo inválido: {period}")
        return None

    from_ts = int(from_dt.timestamp() * 1000)
    
    logger.info(
        f"📊 Consultando {period.value}: "
        f"from={from_dt.isoformat()} to={now_dt.isoformat()} "
        f"(bucket={bucket_duration_ms}ms, esperados={expected_buckets} buckets)"
    )

    try:
        # Verificar que la serie existe
        if not redis_client.exists(watts_key):
            logger.error(f"Serie no existe: {watts_key}")
            return None

        # ✅ FIX: Usar TS.RANGE con agregación correcta
        raw_result = redis_client.execute_command(
            'TS.RANGE', 
            watts_key, 
            from_ts,  # Desde
            now_ts,   # Hasta
            'ALIGN', 'start',  # Alinear al inicio de cada bucket
            'AGGREGATION', 'avg', bucket_duration_ms  # Promedio por bucket
        )

        if not raw_result:
            logger.warning(f"No se obtuvieron datos de {watts_key}")
            return None

        logger.info(f"✅ Buckets obtenidos: {len(raw_result)} (esperados: {expected_buckets})")

        # ✅ FIX: Procesar correctamente watts → kWh
        data_points = []
        for item in raw_result:
            ts = int(item[0])
            avg_watts = float(item[1]) if item[1] is not None else 0.0
            
            # Convertir timestamp a datetime UTC
            dt_object = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            
            # ✅ FIX: Convertir watts promedio a kWh correctamente
            # kWh = (Watts promedio * horas en el bucket) / 1000
            bucket_hours = (bucket_duration_ms / 1000) / 3600.0
            kwh_value = (avg_watts * bucket_hours) / 1000.0
            
            data_points.append({
                "timestamp": dt_object.isoformat(),
                "value": round(kwh_value, 6)
            })
            
            logger.debug(
                f"  Bucket: ts={dt_object.isoformat()}, "
                f"avg_watts={avg_watts:.2f}W, kwh={kwh_value:.6f}"
            )

        logger.info(f"✅ {len(data_points)} puntos procesados correctamente")
        
        return {
            "period": period.value,
            "unit": "kWh",
            "data_points": data_points
        }

    except Exception as e:
        logger.exception(f"❌ Error en get_history_data: {e}")
        return None


def get_last_7_days_data(db, redis_client, user_id: int):
    """
    Recupera datos de los últimos 7 días con promedios diarios.
    
    ✅ FIXES:
    1. Maneja timezone UTC correctamente
    2. Agrupa por fecha correctamente
    3. Devuelve labels en formato ISO
    """
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=7)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)

    logger.info(f"📊 Consultando últimos 7 días: {start_time.isoformat()} → {now.isoformat()}")

    # Buscar series del usuario
    keys = redis_client.keys(f"ts:user:{user_id}:device:*:watts")
    if not keys:
        logger.warning(f"No se encontraron series para user {user_id}")
        return None

    # Diccionario global por fecha
    grouped = defaultdict(lambda: {"watts": [], "volts": [], "amps": []})

    for key in keys:
        key = key.decode() if isinstance(key, bytes) else key
        device_id = key.split(":")[5]

        # Obtener datos de las 3 series
        watts_data = redis_client.ts().range(key, start_ts, end_ts)
        volts_data = redis_client.ts().range(key.replace("watts", "volts"), start_ts, end_ts)
        amps_data  = redis_client.ts().range(key.replace("watts", "amps"),  start_ts, end_ts)

        logger.info(f"  Device {device_id}: {len(watts_data)} watts, {len(volts_data)} volts, {len(amps_data)} amps")

        # Agrupar por fecha (solo la parte de la fecha, sin hora)
        for ts, value in watts_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["watts"].append(float(value))
        
        for ts, value in volts_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["volts"].append(float(value))
        
        for ts, value in amps_data:
            date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            grouped[date]["amps"].append(float(value))

    # Calcular promedios diarios
    sorted_dates = sorted(grouped.keys())
    labels, watts_list, volts_list, amps_list = [], [], [], []

    logger.info(f"📅 Días con datos: {len(sorted_dates)}")

    for date in sorted_dates:
        measures = grouped[date]
        
        avg_watts = sum(measures["watts"]) / len(measures["watts"]) if measures["watts"] else 0
        avg_volts = sum(measures["volts"]) / len(measures["volts"]) if measures["volts"] else 0
        avg_amps  = sum(measures["amps"]) / len(measures["amps"]) if measures["amps"] else 0
        
        # ✅ FIX: Convertir fecha a formato ISO con timezone UTC
        date_iso = (
            datetime.strptime(date, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .isoformat()
        )
        
        labels.append(date_iso)
        watts_list.append(round(avg_watts, 2))
        volts_list.append(round(avg_volts, 2))
        amps_list.append(round(avg_amps, 2))
        
        logger.debug(
            f"  {date}: watts={avg_watts:.2f}W, volts={avg_volts:.2f}V, amps={avg_amps:.2f}A "
            f"({len(measures['watts'])} mediciones)"
        )

    logger.info(f"✅ {len(labels)} días procesados correctamente")

    return {
        "labels": labels,
        "watts": watts_list,
        "volts": volts_list,
        "amps": amps_list
    }