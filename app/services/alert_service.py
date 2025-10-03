
from sqlalchemy.orm import Session
from app.repositories import AlertRepository
from app.schemas import AlertResponse
from app.core import logger

def get_alerts_by_user_service(db: Session, user_id: int) -> list[AlertResponse]:
    """
    Obtiene todas las alertas para un usuario específico.
    """
    alert_repo = AlertRepository(db)
    alerts = alert_repo.get_alerts_by_user(user_id)
    logger.info(f"Se obtuvieron {len(alerts)} alertas para el usuario {user_id}")
    return [AlertResponse.model_validate(alert) for alert in alerts]

# La lógica para CREAR alertas (create_alert_service) la añadiremos aquí
# cuando tengamos la integración con Redis, ya que se basará en el análisis
# de esos datos en tiempo real.