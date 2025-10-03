
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, status, HTTPException

from database import get_db
from schemas import UserLogin, TokenResponse, TokenRefreshRequest
from services import login_for_access_token, refresh_access_token, logout_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login_route(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Inicia sesión y devuelve un token de acceso y uno de refresco.
    """
    return login_for_access_token(db, user_data)

@router.post("/refresh", response_model=TokenResponse)
def refresh_token_route(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    """
    Recibe un token de refresco y devuelve un nuevo token de acceso.
    """
    return refresh_access_token(db, request.refresh_token)

@router.post("/logout")
def logout_route(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    """
    Invalida el token de refresco del usuario para cerrar la sesión de forma segura.
    """
    logout_user(db, request.refresh_token)
    return {"message": "Cierre de sesión exitoso"}