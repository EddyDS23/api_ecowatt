# app/services/dashboard_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from app.repositories import TarrifRepository, UserRepository, RecommendationRepository
from app.core import logger, settings

def get_dashboard_summary(db: Session, redis_client: Redis, user_id: int):
    # 1️⃣ Obtener usuario
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user:
        return {"error": "Usuario no encontrado."}

    # 2️⃣ Fechas del ciclo (usar hora LOCAL, no UTC)
    now_local = datetime.now()  # ← importante: sin timezone.utc
    billing_day = user.user_billing_day

    try:
        if now_local.day >= billing_day:
            start_date = now_local.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = (now_local - relativedelta(months=1)).replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        last_day_prev_month = (now_local.replace(day=1) - timedelta(days=1))
        start_date = last_day_prev_month.replace(day=billing_day) if now_local.day < billing_day else now_local.replace(day=billing_day)

    end_date = (start_date + relativedelta(months=1)) - timedelta(seconds=1)

    # Convertir a timestamps en milisegundos (sin UTC)
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(now_local.timestamp() * 1000)

    # 3️⃣ Leer datos de Redis
    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        return {"error": "El usuario no tiene dispositivos activos."}

    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
    total_kwh = 0.0

    try:
        data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)
        if not data:
            # 🔍 Si no hay datos, probamos sin límites por diagnóstico
            logger.warning(f"No se encontraron datos para {watts_key} entre {start_ts}–{end_ts}, probando rango completo…")
            data = redis_client.ts().range(watts_key, "-", "+")
        
        if len(data) > 1:
            total_watt_seconds = 0
            for i in range(1, len(data)):
                dt = (data[i][0] - data[i-1][0]) / 1000  # ms → s
                avg_watts = (float(data[i][1]) + float(data[i-1][1])) / 2
                total_watt_seconds += avg_watts * dt
            total_kwh = total_watt_seconds / 3_600_000
    except Exception as e:
        logger.error(f"Error leyendo Redis ({watts_key}): {e}")
        total_kwh = 0.0

    # 4️⃣ Tarifa
    tariff_repo = TarrifRepository(db)
    tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, now_local.date())
    if not tariffs:
        return {"error": f"No se encontraron tarifas para '{user.user_trf_rate}'."}

    estimated_cost = 0.0
    kwh_remaining = total_kwh

    if user.user_trf_rate == "DAC" and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
        estimated_cost += float(tariffs[0].trf_fixed_charge_mxn or 0.0)

    for t in tariffs:
        if kwh_remaining <= 0:
            break
        tier_limit = (t.trf_upper_limit_kwh or float('inf')) - t.trf_lower_limit_kwh
        kwh_this_tier = min(kwh_remaining, tier_limit)
        estimated_cost += kwh_this_tier * float(t.trf_price_per_kwh)
        kwh_remaining -= kwh_this_tier

    # 5️⃣ Huella de carbono
    co2 = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
    trees = co2 / 22

    # 6️⃣ Última recomendación
    rec_repo = RecommendationRepository(db)
    rec = rec_repo.get_latest_recommendation_by_user(user_id)
    latest_text = rec.rec_text if rec else None

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
