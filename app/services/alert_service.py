# app/services/alert_service.py 

from sqlalchemy.orm import Session
from app.repositories import AlertRepository, DeviceRepository
from app.schemas import AlertResponse
from app.core import logger
from .recommendation_service import generate_recommendation_with_gemini
from .notification_service import send_push_notification

def get_alerts_by_user_service(db: Session, user_id: int) -> list[AlertResponse]:
    alert_repo = AlertRepository(db)
    alerts = alert_repo.get_alerts_by_user(user_id)
    logger.info(f"Se obtuvieron {len(alerts)} alertas para el usuario {user_id}")
    return [AlertResponse.model_validate(alert) for alert in alerts]

def create_alert_and_recommendation(db: Session, user_id: int, device_name: str, device_id:int, alert_type: str, value: str):
    """
    Crea un registro de alerta en la BD y luego solicita una recomendación a la IA.
    """
    alert_repo = AlertRepository(db)
    
    # 1. Definir el contenido de la alerta 
    if alert_type == "VAMPIRE_CONSUMPTION":
        title = "🕵🏻Consumo Nocturno Detectado"
        # El device_name ahora se interpreta como el nombre del circuito, ej: "Cocina"
        body = f"Hemos detectado un consumo base de {value} en tu circuito '{device_name}' durante la noche. ¡Podrías tener un 'vampiro' eléctrico!"
    elif alert_type == "HIGH_CONSUMPTION_PEAK":
        title = "⚡ Pico de Consumo Detectado"
        body = f"Se registró un consumo elevado y sostenido de {value} en '{device_name}'. ¿Hay algún aparato de alto consumo encendido?" 
    else:
        title = "Alerta de Consumo"
        body = f"Se detectó un evento en el circuito '{device_name}' con valor {value}."

    # 2. Guardar la alerta en la base de datos (sin cambios)
    new_alert = alert_repo.create_alert(user_id, title, body)
    if not new_alert:
        logger.error(f"No se pudo crear la alerta en la BD para user {user_id}, device {device_id}.")
        return
    
    logger.info(f"Alerta creada (ID: {new_alert.ale_id}) para user {user_id}, device {device_id}.")

    # 3. Enviar la notificacion push al usuario
    try:
        device_repo = DeviceRepository(db)
        device = device_repo.get_device_by_id_repository(device_id)

        if device and device.dev_fcm_token:
            logger.info(f"Intentando enviar notificación push para alerta {new_alert.ale_id} a token {device.dev_fcm_token[:10]}...")

            send_push_notification(
                token=device.dev_fcm_token,
                title=title,
                body=body,
                data={'alertId': str(new_alert.ale_id), 'alertType': alert_type}
            )
        elif device:
            logger.warning(f"Dispositivo {device_id} (User {user_id}) no tiene token FCM registrado. No se envió notificación.")
        else:
            logger.error(f"No se encontró el dispositivo {device_id} al intentar enviar notificación para alerta {new_alert.ale_id}.")
    except Exception as e:
        logger.error(f"Error al intentar buscar token o enviar notificación para alerta {new_alert.ale_id}: {e}")
        
    

    # 4. Disparar la generación de la recomendación con IA (sin cambios)
    logger.info(f"Alerta creada (ID: {new_alert.ale_id}). Solicitando recomendación a Gemini...")
    generate_recommendation_with_gemini(
        db=db,
        user_id=user_id,
        alert_type=alert_type,
        device_name=device_name,
        value=value
    )

    