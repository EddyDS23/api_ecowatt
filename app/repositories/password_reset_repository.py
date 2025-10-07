
from sqlalchemy.orm import Session
from app.models.password_reset_token import PasswordResetToken
from datetime import datetime

class PasswordResetRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_token(self, user_id: int, token: str, expires_at: datetime) -> PasswordResetToken:
        db_token = PasswordResetToken(prt_user_id=user_id, prt_token=token, prt_expires_at=expires_at)
        self.db.add(db_token)
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_token(self, token: str) -> PasswordResetToken | None:
        return self.db.query(PasswordResetToken).filter(PasswordResetToken.prt_token == token).first()

    def delete_token(self, token_id: int):
        db_token = self.db.query(PasswordResetToken).filter(PasswordResetToken.prt_id == token_id).first()
        if db_token:
            self.db.delete(db_token)
            self.db.commit()