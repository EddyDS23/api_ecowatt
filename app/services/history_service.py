# app/services/history_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta
from app.repositories import UserRepository
from app.core import logger
from app.schemas import HistoryPeriod
from collections import defaultdict

def get_history_data(db: Session, redis_client: Redis, user_id: int, period: HistoryPeriod):
    """
    Devuelve data_points agrupados para el periodo pedido:
     - daily  -> últimas 24h, bucket = 1 hora  (24 puntos)
     - weekly -> últimos 7d,  bucket = 1 día   (7 puntos)
     - monthly-> últimos 30d, bucket = 1 día   (30 puntos)
    """
    logger.info(f"📊 ============================================")
    logger.info(f"📊 SOLICITUD DE GRÁFICA: {period.value.upper()}")
    logger.info(f"📊 Usuario ID: {user_id}")
    logger.info(f"📊 ============================================")
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user or not getattr(user, "devices", None):
        logger.warning(f"❌ Usuario {user_id} no encontrado o sin dispositivos")
        return None

    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        logger.warning(f"❌ Usuario {user_id} no tiene dispositivos activos")
        return None

    logger.info(f"✅ Dispositivo activo: {active_device.dev_name} (ID: {active_device.dev_id})")
    
    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
    logger.info(f"🔑 Key de Redis: {watts_key}")

    # CRÍTICO: Usar hora LOCAL del servidor (CST)
    now_dt = datetime.now()
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
        logger.error(f"❌ Periodo no válido: {period}")
        return None

    from_ts = int(from_dt.timestamp() * 1000)

    logger.info(f"⏰ Rango de consulta:")
    logger.info(f"   Desde: {from_dt} ({from_ts})")
    logger.info(f"   Hasta: {now_dt} ({now_ts})")
    logger.info(f"   Duración bucket: {bucket_duration_ms / (60*60*1000):.1f} horas")
    logger.info(f"   Buckets esperados: {expected_buckets}")

    try:
        if not redis_client.exists(watts_key):
            logger.warning(f"⚠️ No existe la key en Redis: {watts_key}")
            return _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets)

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
        import traceback
        logger.error(traceback.format_exc())
        return None


def _get_data_with_timeseries(redis_client, watts_key, from_ts, now_ts, bucket_duration_ms, expected_buckets, period):
    """Obtiene datos usando RedisTimeSeries con agregación"""
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

        if len(aggregated_data) == 0:
            logger.warning(f"⚠️  No se encontraron datos en el rango especificado")
        else:
            logger.info(f"📊 Buckets recibidos de Redis:")
            for i, (ts, value) in enumerate(aggregated_data[:5]):
                dt = datetime.fromtimestamp(ts / 1000)
                logger.info(f"   [{i}] {dt} → {value:.2f}W")
            if len(aggregated_data) > 5:
                logger.info(f"   ... y {len(aggregated_data) - 5} buckets más")

        # Crear mapa de datos normalizados
        data_map = {}
        total_watts_sum = 0
        for ts, value in aggregated_data:
            normalized_ts = (ts // bucket_duration_ms) * bucket_duration_ms
            watts_value = float(value) if value is not None else 0.0
            data_map[normalized_ts] = watts_value
            total_watts_sum += watts_value

        avg_watts = total_watts_sum / len(aggregated_data) if aggregated_data else 0
        logger.info(f"📈 Promedio de Watts en periodo: {avg_watts:.2f}W")

        # Generar TODOS los buckets esperados
        # IMPORTANTE: Normalizar from_ts
        normalized_from_ts = (from_ts // bucket_duration_ms) * bucket_duration_ms
        current_ts = normalized_from_ts
        
        logger.info(f"🔨 Generando {expected_buckets} data points...")
        logger.info(f"   Inicio normalizado: {datetime.fromtimestamp(normalized_from_ts / 1000)}")
        
        data_points = []
        total_kwh = 0
        points_with_data = 0
        
        for i in range(expected_buckets):
            bucket_start = current_ts
            dt_object = datetime.fromtimestamp(bucket_start / 1000)
            
            avg_power_watts = data_map.get(bucket_start, 0.0)
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
        if points_with_data > 0:
            logger.info(f"⚡ Promedio por punto: {total_kwh/points_with_data:.4f} kWh")
        else:
            logger.info(f"⚡ Promedio: N/A")
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
                    import json
                    v = float(json.loads(val).get("watts", 0))
                except Exception:
                    v = 0.0
            bucket_start = ((int(score) - from_ts) // bucket_duration_ms) * bucket_duration_ms + from_ts
            if bucket_start in buckets:
                buckets[bucket_start]["sum"] += v
                buckets[bucket_start]["count"] += 1

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
            data_points.append({"timestamp": dt_object, "value": round(kwh_value, 6)})

        logger.info(f"✅ Generados {len(data_points)} puntos con ZSET para '{period.value}'")
        return {"period": period.value, "data_points": data_points}
    except Exception as e:
        logger.error(f"Error en _get_data_with_zset_fallback: {e}")
        raise


def _generate_empty_response(period, from_ts, bucket_duration_ms, expected_buckets):
    """Genera respuesta vacía con todos los buckets en 0"""
    data_points = []
    current_ts = from_ts
    for _ in range(expected_buckets):
        dt_object = datetime.fromtimestamp(current_ts / 1000)
        data_points.append({"timestamp": dt_object, "value": 0.0})
        current_ts += bucket_duration_ms
    logger.info(f"⚠️ Generados {expected_buckets} puntos vacíos (sin datos en Redis)")
    return {"period": period.value, "data_points": data_points}


def get_last_7_days_data(db, redis_client, user_id: int):
    """
    Recupera datos de los últimos 7 días y devuelve data_points con kWh.
    GARANTIZA 7 PUNTOS COMPLETOS.
    """
    logger.info(f"📊 ============================================")
    logger.info(f"📊 SOLICITUD: ÚLTIMOS 7 DÍAS")
    logger.info(f"📊 Usuario ID: {user_id}")
    logger.info(f"📊 ============================================")
    
    # Usar hora LOCAL del servidor (CST)
    now = datetime.now()
    start_time = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(now.timestamp() * 1000)

    logger.info(f"⏰ Rango de consulta:")
    logger.info(f"   Desde: {start_time} ({start_ts})")
    logger.info(f"   Hasta: {now} ({end_ts})")

    keys = redis_client.keys(f"ts:user:{user_id}:device:*:watts")
    if not keys:
        logger.warning(f"⚠️ No se encontraron keys para user {user_id}")
        return _generate_empty_7_days_response(start_time)

    logger.info(f"✅ Encontradas {len(keys)} keys de dispositivos")

    grouped_measurements = defaultdict(list)
    for key in keys:
        key_str = key.decode() if isinstance(key, bytes) else key
        logger.info(f"🔑 Procesando: {key_str}")
        
        try:
            watts_data = redis_client.ts().range(key_str, start_ts, end_ts)
            logger.info(f"   📥 Puntos obtenidos: {len(watts_data)}")
            
            for ts, value in watts_data:
                dt = datetime.fromtimestamp(ts / 1000)
                date_str = dt.strftime("%Y-%m-%d")
                grouped_measurements[date_str].append({"timestamp": ts, "watts": float(value)})
        except Exception as e:
            logger.error(f"❌ Error procesando key {key_str}: {e}")
            continue

    logger.info(f"📊 Datos agrupados por fecha:")
    for date in sorted(grouped_measurements.keys()):
        logger.info(f"   {date}: {len(grouped_measurements[date])} mediciones")

    data_points = []
    total_kwh = 0
    days_with_data = 0
    
    for i in range(7):
        date_obj = start_time + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        timestamp_iso = date_obj.isoformat() + "Z"
        day_measurements = grouped_measurements.get(date_str, [])

        if not day_measurements:
            data_points.append({"timestamp": timestamp_iso, "value": 0.0})
            logger.info(f"   ⚪ {date_str}: Sin datos → 0.0000 kWh")
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
            
            total_kwh += kwh_value
            days_with_data += 1
            
            avg_watts = sum(m["watts"] for m in day_measurements) / len(day_measurements)
            logger.info(f"   ✅ {date_str}: {len(day_measurements)} mediciones → Promedio {avg_watts:.2f}W = {kwh_value:.4f} kWh")

    logger.info(f"📊 ============================================")
    logger.info(f"📊 RESUMEN ÚLTIMOS 7 DÍAS")
    logger.info(f"📊 ============================================")
    logger.info(f"✅ Total de días: 7")
    logger.info(f"📈 Días con datos: {days_with_data}")
    logger.info(f"📉 Días vacíos: {7 - days_with_data}")
    logger.info(f"⚡ Total kWh: {total_kwh:.4f} kWh")
    if days_with_data > 0:
        logger.info(f"⚡ Promedio diario: {total_kwh/days_with_data:.4f} kWh")
    else:
        logger.info(f"⚡ Promedio: N/A")
    logger.info(f"📊 ============================================")

    return {"unit": "kWh", "data_points": data_points}


def _generate_empty_7_days_response(start_time):
    """Genera respuesta vacía con 7 días de ceros"""
    data_points = []
    for i in range(7):
        date_obj = start_time + timedelta(days=i)
        timestamp_iso = date_obj.isoformat() + "Z"
        data_points.append({"timestamp": timestamp_iso, "value": 0.0})
    logger.info(f"⚠️ Generados 7 data_points vacíos (sin datos)")
    return {"unit": "kWh", "data_points": data_points}