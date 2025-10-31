# app/services/dashboard_service.py
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from app.repositories import TarrifRepository, UserRepository, RecommendationRepository
from app.core import logger, settings

def get_dashboard_summary(db: Session, redis_client: Redis, user_id: int):
    try:
        # 1️⃣ Obtener usuario
        user_repo = UserRepository(db)
        user = user_repo.get_user_id_repository(user_id)
        if not user:
            logger.error(f"Usuario {user_id} no encontrado en DB.")
            return {"error": "Usuario no encontrado."}
        logger.info(f"Usuario encontrado: {user.user_name}, tarifa: {user.user_trf_rate}")

        # 2️⃣ Fechas del ciclo de facturación (ahora en UTC)
        now_utc = datetime.now(timezone.utc)
        billing_day = user.user_billing_day
        try:
            if now_utc.day >= billing_day:
                start_date = now_utc.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = (now_utc - relativedelta(months=1)).replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
        except ValueError as ve:
            last_day_prev_month = (now_utc.replace(day=1) - timedelta(days=1))
            start_date = last_day_prev_month.replace(day=billing_day) if now_utc.day < billing_day else now_utc.replace(day=billing_day)
            logger.warning(f"Error ajustando start_date: {ve}, usando {start_date}")

        end_date = (start_date + relativedelta(months=1)) - timedelta(seconds=1)

        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(now_utc.timestamp() * 1000)
        logger.info(f"Rango Redis calculado: {start_ts} → {end_ts} ({start_date} → {now_utc})")

        # 3️⃣ Seleccionar dispositivo activo
        active_device = next((d for d in user.devices if d.dev_status), None)
        if not active_device:
            logger.error(f"Usuario {user_id} no tiene dispositivos activos.")
            return {"error": "El usuario no tiene dispositivos activos."}
        logger.info(f"Dispositivo activo: {active_device.dev_id}")

        # 4️⃣ Leer datos de Redis
        watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
        total_kwh = 0.0
        try:
            data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)
            logger.info(f"Datos obtenidos de Redis: {len(data)} puntos")
            
            if not data:
                logger.warning(f"No se encontraron datos en rango {start_ts}-{end_ts}, probando todo el rango...")
                data = redis_client.ts().range(watts_key, "-", "+")
                logger.info(f"Datos totales en Redis: {len(data)} puntos")

            if len(data) < 2:
                logger.warning(f"No hay suficientes puntos para cálculo kWh. Puntos obtenidos: {len(data)}")
            else:
                total_watt_seconds = 0
                for i in range(1, len(data)):
                    try:
                        t0, t1 = data[i-1][0], data[i][0]
                        v0, v1 = float(data[i-1][1]), float(data[i][1])
                        dt = (t1 - t0) / 1000  # ms → s
                        avg_watts = (v0 + v1) / 2
                        total_watt_seconds += avg_watts * dt
                    except Exception as e:
                        logger.error(f"Error procesando punto {i}: {data[i]} → {e}")
                total_kwh = total_watt_seconds / 3_600_000
                logger.info(f"Total kWh calculado: {total_kwh:.4f}")
        except Exception as e:
            logger.error(f"Error leyendo Redis ({watts_key}): {e}")
            total_kwh = 0.0

        # 5️⃣ Calcular tarifa
        estimated_cost = 0.0
        kwh_remaining = total_kwh
        tariff_repo = TarrifRepository(db)
        tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, now_utc.date())
        if not tariffs:
            logger.error(f"No se encontraron tarifas para {user.user_trf_rate}")
            return {"error": f"No se encontraron tarifas para '{user.user_trf_rate}'."}

        logger.info(f"{len(tariffs)} tramos tarifarios encontrados.")
        if user.user_trf_rate == "DAC" and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
            estimated_cost += float(tariffs[0].trf_fixed_charge_mxn or 0.0)

        for t in tariffs:
            if kwh_remaining <= 0:
                break
            tier_limit = (t.trf_upper_limit_kwh or float('inf')) - (t.trf_lower_limit_kwh or 0)
            kwh_this_tier = min(kwh_remaining, tier_limit)
            estimated_cost += kwh_this_tier * float(t.trf_price_per_kwh)
            kwh_remaining -= kwh_this_tier
        logger.info(f"Costo estimado calculado: {estimated_cost:.2f} MXN")

        # 6️⃣ Huella de carbono
        co2 = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
        trees = co2 / 22
        logger.info(f"CO2 emitido: {co2:.2f} kg → equivalente a {trees:.4f} árboles")

        # 7️⃣ Última recomendación
        rec_repo = RecommendationRepository(db)
        rec = rec_repo.get_latest_recommendation_by_user(user_id)
        latest_text = rec.rec_text if rec else None
        logger.info(f"Última recomendación: {latest_text}")

        # ✅ Resultado final
        return {
            "kwh_consumed_cycle": round(total_kwh, 2),
            "estimated_cost_mxn": round(estimated_cost, 2),
            "billing_cycle_start": start_date.date(),
            "billing_cycle_end": end_date.date(),
            "days_in_cycle": (now_utc.date() - start_date.date()).days,
            "current_tariff": user.user_trf_rate,
            "carbon_footprint": {
                "co2_emitted_kg": round(co2, 2),
                "equivalent_trees_absorption_per_year": round(trees, 4)
            },
            "latest_recommendation": latest_text
        }

    except Exception as e:
        logger.exception(f"Error general en get_dashboard_summary para user {user_id}: {e}")
        return {"error": "Ocurrió un error al generar el dashboard."}