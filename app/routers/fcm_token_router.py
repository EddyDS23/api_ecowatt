from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.core import TokenData, get_current_user
from app.repositories import FCMTokenRepository

router = APIRouter(prefix="/fcm", tags=["FCM"])

class FCMTokenRequest(BaseModel):
    fcm_token: str = Field(..., min_length=100)
    device_name: str | None = None
    platform: str | None = None

@router.post("/register")
def register_fcm_token(
    data: FCMTokenRequest,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Registra un token FCM"""
    repo = FCMTokenRepository(db)
    success = repo.create_or_update(
        user_id=current_user.user_id,
        token=data.fcm_token,
        device_name=data.device_name,
        platform=data.platform
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Error registrando token")
    
    return {"message": "Token registrado"}