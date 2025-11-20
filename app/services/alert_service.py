# app/services/alert_service.py 

from sqlalchemy.orm import Session
from app.repositories import AlertRepository, DeviceRepository, FCMTokenRepository
from app.schemas import AlertResponse
from app.core import logger
from .recommendation_service import generate_recommendation_with_gemini
from .notification_service import send_push_notification

def get_alerts_by_user_service(db: Session, user_id: int) -> list[AlertResponse]:
    alert_repo = AlertRepository(db)
    alerts = alert_repo.get_alerts_by_user(user_id)
    logger.info(f"Se obtuvieron {len(alerts)} alertas para el usuario {user_id}")
    return [AlertResponse.model_validate(alert) for alert in alerts]

def create_alert_and_recommendation(
    db: Session, 
    user_id: int, 
    device_name: str, 
    device_id: int, 
    alert_type: str, 
    value: str
):
    alert_repo = AlertRepository(db)
    
    # 1. Contenido
    if alert_type == "VAMPIRE_CONSUMPTION":
        title = "🕵🏻 Consumo Nocturno Detectado"
        body = f"Detectamos {value} en '{device_name}' durante la noche."
    elif alert_type == "HIGH_CONSUMPTION_PEAK":
        title = "⚡ Pico de Consumo Detectado"
        body = f"Consumo elevado de {value} en '{device_name}'."
    else:
        title = "Alerta de Consumo"
        body = f"Evento en '{device_name}': {value}."

    # 2. Guardar alerta
    new_alert = alert_repo.create_alert(user_id, title, body)
    if not new_alert:
        return
    
    # 3. ENVIAR A TODOS LOS TOKENS DEL USUARIO
    try:
        fcm_repo = FCMTokenRepository(db)
        tokens = fcm_repo.get_active_tokens(user_id)
        
        if tokens:
            for fcm_token in tokens:
                try:
                    send_push_notification(
                        token=fcm_token.fcm_token,
                        title=title,
                        body=body,
                        data={'alertId': str(new_alert.ale_id), 'deviceId': str(device_id)}
                    )
                except Exception as e:
                    logger.error(f"Error enviando notificación: {e}")
    except Exception as e:
        logger.error(f"Error general: {e}")
    
    # 4. Recomendación IA
    generate_recommendation_with_gemini(db=db, user_id=user_id, alert_type=alert_type, device_name=device_name, value=value)

    