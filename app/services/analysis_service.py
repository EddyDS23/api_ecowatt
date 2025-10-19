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

# --- CONSTANTES PARA PICOS ---
HIGH_PEAK_THRESHOLD_WATTS = 1500 # Umbral en Watts (ajusta según necesites)
HIGH_PEAK_MIN_DURATION_MINUTES = 5 # Duración mínima en minutos
HIGH_PEAK_ANALYSIS_HOURS = 3 # Cuántas horas hacia atrás analizar para picos

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

            # 2. Detectar Picos Inusuales
            _detect_high_peak(db,redis_client,device)

    except Exception as e:
        # Captura errores generales durante el análisis de todos los dispositivos
        logger.error(f"Error general en analyze_consumption_patterns: {e}")
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


def _detect_high_peak(db: Session, redis_client: Redis, device):
    """
    Analiza datos recientes para detectar picos de consumo sostenidos.
    """
    try:
        now_utc = datetime.now(timezone.utc)
        start_time_dt = now_utc - timedelta(hours=HIGH_PEAK_ANALYSIS_HOURS)
        end_ts = int(now_utc.timestamp() * 1000)
        start_ts = int(start_time_dt.timestamp() * 1000)

        watts_key = f"ts:user:{device.dev_user_id}:device:{device.dev_id}:watts"

        if not redis_client.exists(watts_key):
            # No es un warning, es normal si no hay datos recientes
            logger.debug(f"No se encontró la serie {watts_key} para análisis de picos.")
            return

        # Obtener datos del rango de tiempo especificado
        # Usamos '-' y '+' en TS.RANGE para obtener timestamps y valores
        data = redis_client.ts().range(watts_key, from_time=start_ts, to_time=end_ts)

        if not data or len(data) < 2:
            logger.debug(f"No hay suficientes datos recientes en {watts_key} para análisis de picos.")
            return

        peak_start_time = None
        max_peak_value = 0

        for i in range(len(data)):
            current_ts_ms, current_value_str = data[i]
            try:
                current_value = float(current_value_str)
            except (ValueError, TypeError):
                continue # Ignora puntos con valores no numéricos

            if current_value > HIGH_PEAK_THRESHOLD_WATTS:
                if peak_start_time is None:
                    # Marca el inicio del posible pico
                    peak_start_time = current_ts_ms
                    max_peak_value = current_value
                else:
                    # Actualiza el valor máximo visto durante este pico
                    max_peak_value = max(max_peak_value, current_value)

                # Verifica la duración si llegamos al final de los datos o el valor baja del umbral
                is_last_point = (i == len(data) - 1)
                next_value_below_threshold = False
                if not is_last_point:
                    try:
                         next_value = float(data[i+1][1])
                         if next_value <= HIGH_PEAK_THRESHOLD_WATTS:
                              next_value_below_threshold = True
                    except (ValueError, TypeError):
                         next_value_below_threshold = True # Si el siguiente punto es inválido, termina el pico aquí

                if is_last_point or next_value_below_threshold:
                    # Fin del pico detectado, calcula duración
                    duration_ms = current_ts_ms - peak_start_time
                    duration_minutes = duration_ms / (1000 * 60)

                    if duration_minutes >= HIGH_PEAK_MIN_DURATION_MINUTES:
                        logger.info(f"¡ALERTA! Pico de consumo detectado para {device.dev_name}: {max_peak_value:.2f}W durante {duration_minutes:.1f} min.")
                        # Llama a la función de alertas con el nuevo tipo
                        create_alert_and_recommendation(
                            db=db,
                            user_id=device.dev_user_id,
                            device_id=device.dev_id, # Pasa el ID del dispositivo
                            device_name=device.dev_name,
                            alert_type="HIGH_CONSUMPTION_PEAK", # Nuevo tipo de alerta
                            value=f"{max_peak_value:.2f}W" # Reporta el valor máximo del pico
                        )
                        # Importante: Salir después de detectar y reportar el primer pico largo
                        # para no generar múltiples alertas por el mismo evento largo.
                        return
                    else:
                        # Si el pico fue corto, resetea para buscar el siguiente
                        peak_start_time = None
                        max_peak_value = 0
            else:
                # Si el valor actual está por debajo, resetea el inicio del pico
                peak_start_time = None
                max_peak_value = 0

    except Exception as e:
        logger.error(f"Error detectando picos de consumo para device_id {device.dev_id}: {e}")