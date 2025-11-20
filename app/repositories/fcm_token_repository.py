from sqlalchemy.orm import Session
from app.models import FCMToken
from app.core import logger
from datetime import datetime, timezone
from typing import List

class FCMTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_tokens(self, user_id: int) -> List[FCMToken]:
        """Obtiene todos los tokens de un usuario"""
        return self.db.query(FCMToken).filter(FCMToken.fcm_user_id == user_id).all()

    def create_or_update(self, user_id: int, token: str, device_name: str = None, platform: str = None):
        """Crea o actualiza un token"""
        try:
            existing = self.db.query(FCMToken).filter(FCMToken.fcm_token == token).first()
            
            if existing:
                existing.fcm_last_used = datetime.now(timezone.utc)
                if device_name:
                    existing.fcm_device_name = device_name
                if platform:
                    existing.fcm_platform = platform
            else:
                new_token = FCMToken(
                    fcm_user_id=user_id,
                    fcm_token=token,
                    fcm_device_name=device_name,
                    fcm_platform=platform
                )
                self.db.add(new_token)
            
            self.db.commit()
            logger.info(f"✅ Token FCM registrado para usuario {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error en FCM token: {e}")
            self.db.rollback()
            return False