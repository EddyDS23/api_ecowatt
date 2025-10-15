# app/services/dashboard_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.repositories import TarrifRepository, UserRepository, RecommendationRepository
from app.core import logger, settings

def get_dashboard_summary(db: Session, redis_client: Redis, user_id: int):
    try:
        # 1️⃣ Obtener usuario
        user_repo = UserRepository(db)
        user = user_repo.get_user_id_repository(user_id)
        if not user:
            logger.error(f"Usuario {user_id} no encontrado en la base de datos.")
            return {"error": "Usuario no encontrado."}
    except Exception as e:
        logger.exception(f"Error al obtener usuario {user_id}: {e}")
        return {"error": "Error interno al obtener usuario."}

    # 2️⃣ Fechas del ciclo (hora LOCAL)
    try:
        now_local = datetime.now()
        billing_day = user.user_billing_day
        prev_month = now_local - relativedelta(months=1)

        try:
            if now_local.day >= billing_day:
                start_date = now_local.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = prev_month.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            last_day_prev_month = (now_local.replace(day=1) - timedelta(days=1))
            start_date = last_day_prev_month.replace(
                day=min(billing_day, last_day_prev_month.day),
                hour=0, minute=0, second=0, microsecond=0
            )

        end_date = now_local
        start_ts = int(start_date.timestamp() * 1000)
        end_ts   = int(end_date.timestamp() * 1000)
        logger.info(f"Rango Redis para user {user_id}: {start_ts} → {end_ts} ({start_date} → {end_date})")
    except Exception as e:
        logger.exception(f"Error calculando fechas para usuario {user_id}: {e}")
        return {"error": "Error interno al calcular fechas del ciclo."}

    # 3️⃣ Leer datos de Redis
    try:
        active_device = next((d for d in user.devices if d.dev_status), None)
        if not active_device:
            logger.warning(f"Usuario {user_id} no tiene dispositivos activos.")
            return {"error": "El usuario no tiene dispositivos activos."}

        watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
        total_kwh = 0.0

        try:
            data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)
            if not data:
                logger.warning(f"No se encontraron datos en Redis para {watts_key} entre {start_ts}–{end_ts}. Intentando rango completo...")
                data = redis_client.ts().range(watts_key, "-", "+")
            if not data:
                logger.warning(f"No hay datos en Redis para {watts_key} incluso con rango completo.")
        except Exception as e:
            logger.exception(f"Error consultando Redis para key {watts_key}: {e}")
            data = []

        if len(data) > 1:
            total_watt_seconds = 0
            for i in range(1, len(data)):
                try:
                    dt = (data[i][0] - data[i-1][0]) / 1000  # ms → s
                    avg_watts = (float(data[i][1]) + float(data[i-1][1])) / 2
                    total_watt_seconds += avg_watts * dt
                except Exception as e:
                    logger.exception(f"Error calculando kWh entre puntos {i-1} y {i} para {watts_key}: {e}")
            total_kwh = total_watt_seconds / 3_600_000  # Wh → kWh
    except Exception as e:
        logger.exception(f"Error procesando datos de Redis para usuario {user_id}: {e}")
        total_kwh = 0.0

    # 4️⃣ Tarifa
    try:
        tariff_repo = TarrifRepository(db)
        tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, now_local.date())
        if not tariffs:
            logger.warning(f"No se encontraron tarifas para '{user.user_trf_rate}' en la fecha {now_local.date()}.")
            return {"error": f"No se encontraron tarifas para '{user.user_trf_rate}'."}

        estimated_cost = 0.0
        kwh_remaining = total_kwh

        if user.user_trf_rate == "DAC" and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
            estimated_cost += float(tariffs[0].trf_fixed_charge_mxn or 0.0)

        for t in tariffs:
            try:
                if kwh_remaining <= 0:
                    break
                tier_limit = (t.trf_upper_limit_kwh or float('inf')) - t.trf_lower_limit_kwh
                kwh_this_tier = min(kwh_remaining, tier_limit)
                estimated_cost += kwh_this_tier * float(t.trf_price_per_kwh)
                kwh_remaining -= kwh_this_tier
            except Exception as e:
                logger.exception(f"Error calculando tarifa para usuario {user_id} en tier {t}: {e}")
    except Exception as e:
        logger.exception(f"Error obteniendo tarifas para usuario {user_id}: {e}")
        estimated_cost = 0.0

    # 5️⃣ Huella de carbono
    try:
        co2 = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
        trees = co2 / 22
    except Exception as e:
        logger.exception(f"Error calculando huella de carbono para usuario {user_id}: {e}")
        co2 = 0.0
        trees = 0.0

    # 6️⃣ Última recomendación
    try:
        rec_repo = RecommendationRepository(db)
        rec = rec_repo.get_latest_recommendation_by_user(user_id)
        latest_text = rec.rec_text if rec else None
    except Exception as e:
        logger.exception(f"Error obteniendo recomendación para usuario {user_id}: {e}")
        latest_text = None

    return {
        "kwh_consumed_cycle": round(total_kwh, 2),
        "estimated_cost_mxn": round(estimated_cost, 2),
        "billing_cycle_start": start_date.date(),
        "billing_cycle_end": end_date.date(),
        "days_in_cycle": (now_local.date() - start_date.date()).days,
        "current_tariff": user.user_trf_rate,
        "carbon_footprint": {
            "co2_emitted_kg": round(co2, 2),
            "equivalent_trees_absorption_per_year": round(trees, 4)
        },
        "latest_recommendation": latest_text
    }
