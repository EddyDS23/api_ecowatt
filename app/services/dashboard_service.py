# app/services/dashboard_service.py (VERSIÓN CORREGIDA)

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

        # 2️⃣ Calcular ciclo de facturación ACTIVO
        now_utc = datetime.now(timezone.utc)
        billing_day = user.user_billing_day
        
        # === USAR LA MISMA LÓGICA DEL REPORTE ===
        try:
            if now_utc.day >= billing_day:
                start_date = now_utc.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = (now_utc - relativedelta(months=1)).replace(
                    day=billing_day, hour=0, minute=0, second=0, microsecond=0
                )
        except ValueError:
            # Manejar días inválidos (ej: 31 en febrero)
            import calendar
            if now_utc.day >= billing_day:
                last_day = calendar.monthrange(now_utc.year, now_utc.month)[1]
                start_date = now_utc.replace(
                    day=min(billing_day, last_day),
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:
                prev_month = now_utc - relativedelta(months=1)
                last_day = calendar.monthrange(prev_month.year, prev_month.month)[1]
                start_date = prev_month.replace(
                    day=min(billing_day, last_day),
                    hour=0, minute=0, second=0, microsecond=0
                )

        # Fin del ciclo: 1 mes después - 1 segundo
        end_date = (start_date + relativedelta(months=1)) - timedelta(seconds=1)

        # ✅ CORRECCIÓN CRÍTICA: Usar NOW para cálculo, pero NO exceder end_date
        # El ciclo puede no haber terminado aún
        calculation_end = min(now_utc, end_date)
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(calculation_end.timestamp() * 1000)  # ✅ CAMBIO AQUÍ
        
        logger.info(
            f"📅 Ciclo de facturación: {start_date.date()} → {end_date.date()}\n"
            f"📊 Calculando consumo hasta: {calculation_end.date()}\n"
            f"🔢 Timestamps: {start_ts} → {end_ts}"
        )

        # 3️⃣ Obtener dispositivos activos
        active_devices = [d for d in user.devices if d.dev_status]
        if not active_devices:
            logger.error(f"Usuario {user_id} no tiene dispositivos activos.")
            return {"error": "El usuario no tiene dispositivos activos."}
        
        logger.info(f"Dispositivos activos: {len(active_devices)}")

        # 4️⃣ Calcular consumo TOTAL de TODOS los dispositivos
        total_kwh = 0.0
        devices_with_data = 0
        
        for device in active_devices:
            watts_key = f"ts:user:{user_id}:device:{device.dev_id}:watts"
            
            try:
                # Obtener datos del periodo
                data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)
                logger.info(f"   Device {device.dev_id} ({device.dev_name}): {len(data)} puntos")
                
                if len(data) < 2:
                    logger.warning(f"   ⚠️ Insuficientes datos para device {device.dev_id}")
                    continue
                
                # Calcular kWh usando integración trapezoidal
                device_watt_seconds = 0.0
                MAX_GAP_SECONDS = 60.0
                for i in range(1, len(data)):
                    try:
                        t0, t1 = data[i-1][0], data[i][0]
                        v0, v1 = float(data[i-1][1]), float(data[i][1])
                        dt = (t1 - t0) / 1000.0  # ms → s

                        if dt > MAX_GAP_SECONDS:
                            # Si hay un salto grande, asumimos que el dispositivo estuvo apagado
                            # o desconectado. No sumamos nada en este intervalo.
                            continue

                        avg_watts = (v0 + v1) / 2.0
                        device_watt_seconds += avg_watts * dt
                    except Exception as e:
                        logger.error(f"   Error procesando punto {i}: {e}")
                
                device_kwh = device_watt_seconds / 3_600_000.0
                total_kwh += device_kwh
                devices_with_data += 1
                
                logger.info(f"   ✅ Device {device.dev_id}: {device_kwh:.4f} kWh")
                
            except Exception as e:
                logger.error(f"   ❌ Error leyendo {watts_key}: {e}")
                continue
        
        logger.info(f"💡 Total kWh calculado: {total_kwh:.4f} ({devices_with_data} dispositivos)")

        # 5️⃣ Calcular costo tarifario
        estimated_cost = 0.0
        kwh_remaining = total_kwh
        tariff_repo = TarrifRepository(db)
        tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, now_utc.date())
        
        if not tariffs:
            logger.error(f"No se encontraron tarifas para {user.user_trf_rate}")
            return {"error": f"No se encontraron tarifas para '{user.user_trf_rate}'."}

        logger.info(f"Aplicando {len(tariffs)} tramos tarifarios")
        
        # Cargo fijo (solo DAC)
        if user.user_trf_rate == "DAC" and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
            estimated_cost += float(tariffs[0].trf_fixed_charge_mxn or 0.0)

        # Calcular por tramos
        for tariff in tariffs:
            if kwh_remaining <= 0:
                break
            
            tier_limit = (tariff.trf_upper_limit_kwh or float('inf')) - (tariff.trf_lower_limit_kwh or 0)
            kwh_this_tier = min(kwh_remaining, tier_limit)
            tier_cost = kwh_this_tier * float(tariff.trf_price_per_kwh)
            
            estimated_cost += tier_cost
            kwh_remaining -= kwh_this_tier
            
            logger.debug(
                f"   Tramo '{tariff.trf_level_name}': "
                f"{kwh_this_tier:.2f} kWh × ${tariff.trf_price_per_kwh} = ${tier_cost:.2f}"
            )
        
        logger.info(f"💰 Costo estimado: ${estimated_cost:.2f} MXN")

        # 6️⃣ Huella de carbono
        co2 = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
        trees = co2 / 22
        logger.info(f"🌱 CO₂: {co2:.2f} kg (≈ {trees:.4f} árboles/año)")

        # 7️⃣ Última recomendación
        rec_repo = RecommendationRepository(db)
        rec = rec_repo.get_latest_recommendation_by_user(user_id)
        latest_text = rec.rec_text if rec else None

        # 8️⃣ Calcular días transcurridos en el ciclo
        days_elapsed = (calculation_end.date() - start_date.date()).days

        # ✅ Retornar respuesta
        return {
            "kwh_consumed_cycle": round(total_kwh, 2),
            "estimated_cost_mxn": round(estimated_cost, 2),
            "billing_cycle_start": start_date.date(),
            "billing_cycle_end": end_date.date(),
            "days_in_cycle": days_elapsed,  # ✅ Días TRANSCURRIDOS, no totales
            "current_tariff": user.user_trf_rate,
            "carbon_footprint": {
                "co2_emitted_kg": round(co2, 2),
                "equivalent_trees_absorption_per_year": round(trees, 4)
            },
            "latest_recommendation": latest_text
        }

    except Exception as e:
        logger.exception(f"❌ Error en get_dashboard_summary para user {user_id}: {e}")
        return {"error": "Ocurrió un error al generar el dashboard."}