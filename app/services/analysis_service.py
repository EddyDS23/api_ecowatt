# app/services/analysis_service.py (NUEVO)

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from redis import Redis
from app.database import SessionLocal, get_redis_client
from app.repositories import DeviceRepository
from app.core import logger
from .alert_service import create_alert_and_recommendation # Importación clave

# --- CONSTANTES DE ANÁLISIS ---
VAMPIRE_CONSUMPTION_THRESHOLD_WATTS = 20  # Watts
VAMPIRE_ANALYSIS_START_HOUR_UTC = 7       # 1 AM (CST/Mexico City) es 7 AM UTC
VAMPIRE_ANALYSIS_END_HOUR_UTC = 11      # 5 AM (CST/Mexico City) es 11 AM UTC

def analyze_consumption_patterns():
    """
    Función principal que orquesta el análisis de todos los dispositivos.
    Esta función es llamada por la tarea de Celery.
    """
    db: Session = SessionLocal()
    redis_client: Redis = next(get_redis_client())
    
    try:
        device_repo = DeviceRepository(db)
        active_devices = device_repo.get_all_active_devices()
        logger.info(f"Análisis iniciado para {len(active_devices)} dispositivos activos.")

        for device in active_devices:
            logger.debug(f"Analizando dispositivo: {device.dev_name} (ID: {device.dev_id})")
            
            # 1. Detectar Consumo Vampiro
            _detect_vampire_consumption(db, redis_client, device)

            # 2. (Futuro) Detectar Picos Inusuales
            # _detect_unusual_peaks(db, redis_client, device)

    finally:
        db.close()

def _detect_vampire_consumption(db: Session, redis_client: Redis, device):
    """
    Analiza los datos de las últimas 24 horas para detectar consumo nocturno.
    """
    try:
        now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ts = now_ts - (24 * 60 * 60 * 1000) # 24 horas atrás
        
        watts_key = f"ts:user:{device.dev_user_id}:device:{device.dev_id}:watts"
        
        if not redis_client.exists(watts_key):
            logger.warning(f"No se encontró la serie de tiempo {watts_key} para análisis vampiro.")
            return

        # Obtenemos todos los puntos de las últimas 24 horas
        data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=now_ts)
        
        # Filtramos solo los que están en el horario nocturno (en UTC)
        night_consumption = [
            float(value) for ts, value in data 
            if VAMPIRE_ANALYSIS_START_HOUR_UTC <= datetime.fromtimestamp(ts / 1000, tz=timezone.utc).hour < VAMPIRE_ANALYSIS_END_HOUR_UTC
        ]

        if not night_consumption:
            logger.info(f"No hay datos de consumo nocturno para {device.dev_name}.")
            return

        # Calculamos el promedio de consumo en la noche
        average_night_watts = sum(night_consumption) / len(night_consumption)
        
        logger.debug(f"Consumo nocturno promedio para {device.dev_name}: {average_night_watts:.2f}W")

        # Si el promedio supera nuestro umbral, creamos la alerta
        if average_night_watts > VAMPIRE_CONSUMPTION_THRESHOLD_WATTS:
            logger.info(f"¡ALERTA! Consumo vampiro detectado para {device.dev_name}: {average_night_watts:.2f}W")
            
            # ¡La magia ocurre aquí!
            # Creamos la alerta y disparamos la generación de la recomendación con IA.
            create_alert_and_recommendation(
                db=db,
                user_id=device.dev_user_id,
                device_name=device.dev_name,
                device_id=device.dev_id,
                alert_type="VAMPIRE_CONSUMPTION",
                value=f"{average_night_watts:.2f}W"
            )

    except Exception as e:
        logger.error(f"Error detectando consumo vampiro para device_id {device.dev_id}: {e}")