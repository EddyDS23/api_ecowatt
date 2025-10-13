# app/services/alert_service.py 

from sqlalchemy.orm import Session
from app.repositories import AlertRepository
from app.schemas import AlertResponse
from app.core import logger
from .recommendation_service import generate_recommendation_with_gemini

def get_alerts_by_user_service(db: Session, user_id: int) -> list[AlertResponse]:
    alert_repo = AlertRepository(db)
    alerts = alert_repo.get_alerts_by_user(user_id)
    logger.info(f"Se obtuvieron {len(alerts)} alertas para el usuario {user_id}")
    return [AlertResponse.model_validate(alert) for alert in alerts]

def create_alert_and_recommendation(db: Session, user_id: int, device_name: str, alert_type: str, value: str):
    """
    Crea un registro de alerta en la BD y luego solicita una recomendación a la IA.
    """
    alert_repo = AlertRepository(db)
    
    # 1. Definir el contenido de la alerta 
    if alert_type == "VAMPIRE_CONSUMPTION":
        title = "Consumo Nocturno Detectado"
        # El device_name ahora se interpreta como el nombre del circuito, ej: "Cocina"
        body = f"Hemos detectado un consumo base de {value} en tu circuito '{device_name}' durante la noche. ¡Podrías tener un 'vampiro' eléctrico!"
    else:
        title = "Alerta de Consumo"
        body = f"Se detectó un evento en el circuito '{device_name}' con valor {value}."

    # 2. Guardar la alerta en la base de datos (sin cambios)
    new_alert = alert_repo.create_alert(user_id, title, body)
    if not new_alert:
        logger.error("No se pudo crear la alerta en la base de datos. Abortando recomendación.")
        return

    # 3. Disparar la generación de la recomendación con IA (sin cambios)
    logger.info(f"Alerta creada (ID: {new_alert.ale_id}). Solicitando recomendación a Gemini...")
    generate_recommendation_with_gemini(
        db=db,
        user_id=user_id,
        alert_type=alert_type,
        device_name=device_name,
        value=value
    )