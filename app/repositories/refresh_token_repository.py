from sqlalchemy.orm import Session
from models import RefreshToken
from datetime import datetime

class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_token(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        db_token = RefreshToken(ref_user_id=user_id, ref_token=token, ref_expires_at=expires_at)
        self.db.add(db_token)
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_token(self, token: str) -> RefreshToken | None:
        return self.db.query(RefreshToken).filter(RefreshToken.ref_token == token).first()

    def delete_token(self, token: str):
        db_token = self.get_token(token)
        if db_token:
            self.db.delete(db_token)
            self.db.commit()