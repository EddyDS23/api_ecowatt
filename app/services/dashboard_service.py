# app/services/dashboard_service.py 

from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta, timezone 
from dateutil.relativedelta import relativedelta

from app.repositories import TarrifRepository, UserRepository
from app.core import logger

def get_dashboard_summary(db: Session, redis_client: Redis, user_id: int):
    # 1. Obtener la información del usuario desde PostgreSQL
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if not user:
        return {"error": "Usuario no encontrado."}

    # 2. Calcular las fechas del ciclo de facturación actual (AHORA EN UTC)
    now_utc = datetime.now(timezone.utc)
    billing_day = user.user_billing_day
    
    # Nos aseguramos de manejar el día 29, 30, 31 en meses cortos
    try:
        if now_utc.day >= billing_day:
            start_date = now_utc.replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = (now_utc - relativedelta(months=1)).replace(day=billing_day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError: # Si el día de facturación no existe en el mes (ej. 31 en Febrero)
        last_day_of_prev_month = (now_utc.replace(day=1) - timedelta(days=1))
        start_date = last_day_of_prev_month.replace(day=billing_day) if now_utc.day < billing_day else now_utc.replace(day=billing_day)

    end_date = (start_date + relativedelta(months=1)) - timedelta(seconds=1)

    # Convertir a timestamps en milisegundos para Redis
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(now_utc.timestamp() * 1000) # Hasta el momento actual

    # 3. Obtener el consumo total de kWh desde Redis
    active_device = next((d for d in user.devices if d.dev_status), None)
    if not active_device:
        return {"error": "El usuario no tiene dispositivos activos."}
    
    watts_key = f"ts:user:{user_id}:device:{active_device.dev_id}:watts"
    total_kwh = 0.0

    try:
        measurements = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)
        
        if len(measurements) > 1:
            total_watt_seconds = 0
            for i in range(1, len(measurements)):
                time_diff_seconds = (measurements[i][0] - measurements[i-1][0]) / 1000
                avg_power_watts = (float(measurements[i][1]) + float(measurements[i-1][1])) / 2
                total_watt_seconds += avg_power_watts * time_diff_seconds
            
            total_kwh = total_watt_seconds / 3_600_000 # Conversión de W-s a kWh
    except Exception as e:
        logger.error(f"Error al leer la serie temporal de Redis para {watts_key}: {e}")
        total_kwh = 0.0

    # 4. Obtener las tarifas aplicables desde PostgreSQL
    tariff_repo = TarrifRepository(db)
    tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, now_utc.date())
    
    if not tariffs:
         return {"error": f"No se encontraron tarifas para '{user.user_trf_rate}' en la fecha actual."}

    # 5. Calcular el costo estimado
    estimated_cost = 0.0
    kwh_remaining_to_bill = total_kwh
    
    if user.user_trf_rate == "DAC" and tariffs and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
        estimated_cost += float(tariffs[0].trf_fixed_charge_mxn or 0.0)

    for tariff in tariffs:
        if kwh_remaining_to_bill <= 0:
            break
        
        tier_kwh_limit = (tariff.trf_upper_limit_kwh or float('inf')) - tariff.trf_lower_limit_kwh
        kwh_in_this_tier = min(kwh_remaining_to_bill, tier_kwh_limit)
        
        if kwh_in_this_tier > 0:
            estimated_cost += kwh_in_this_tier * float(tariff.trf_price_per_kwh)
            kwh_remaining_to_bill -= kwh_in_this_tier

    return {
        "kwh_consumed_cycle": round(total_kwh, 2),
        "estimated_cost_mxn": round(estimated_cost, 2),
        "billing_cycle_start": start_date.date(),
        "billing_cycle_end": end_date.date(),
        "days_in_cycle": (now_utc.date() - start_date.date()).days,
        "current_tariff": user.user_trf_rate
    }