from sqlalchemy.orm import Session
from models import Alert
from core import logger

class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, user_id: int, title: str, body: str) -> Alert | None:
        try:
            new_alert = Alert(ale_user_id=user_id, ale_title=title, ale_body=body)
            self.db.add(new_alert)
            self.db.commit()
            self.db.refresh(new_alert)
            logger.info(f"Alerta creada para el usuario {user_id}")
            return new_alert
        except Exception as e:
            logger.error(f"No se pudo crear la alerta: {e}")
            self.db.rollback()
            return None

    def get_alerts_by_user(self, user_id: int) -> list[Alert]:
        return self.db.query(Alert).filter(Alert.ale_user_id == user_id).order_by(Alert.ale_created_at.desc()).all()