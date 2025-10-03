

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import secrets

from repositories import UserRepository, RefreshTokenRepository
from schemas import UserLogin, TokenResponse
from core import logger, settings, security

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def login_for_access_token(db: Session, user_data: UserLogin) -> TokenResponse:
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email_repository(user_data.user_email)
    
    if not user or not pwd_context.verify(user_data.user_password, user.user_password):
        logger.warning(f"Fallo de autenticación para el email: {user_data.user_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Crear Access Token de corta duración
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_token(
        data={"user_id": user.user_id}, expires_delta=access_token_expires
    )

    # 2. Crear Refresh Token de larga duración
    refresh_token_expires = timedelta(days=30)
    refresh_token_str = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + refresh_token_expires
    
    # 3. Guardar el Refresh Token en la base de datos
    token_repo = RefreshTokenRepository(db)
    token_repo.create_token(user_id=user.user_id, token=refresh_token_str, expires_at=expires_at)

    logger.info(f"Usuario {user.user_email} ha iniciado sesión exitosamente.")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        token_type="Bearer"
    )

def refresh_access_token(db: Session, refresh_token_str: str) -> TokenResponse:
    token_repo = RefreshTokenRepository(db)
    refresh_token = token_repo.get_token(refresh_token_str)

    # Validar que el token de refresco exista y no haya expirado
    if not refresh_token or refresh_token.ref_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generar un nuevo access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = security.create_token(
        data={"user_id": refresh_token.ref_user_id}, expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=refresh_token_str, # Se devuelve el mismo refresh token
        token_type="Bearer"
    )

def logout_user(db: Session, refresh_token_str: str):
    token_repo = RefreshTokenRepository(db)
    token_repo.delete_token(refresh_token_str)
    logger.info("Usuario ha cerrado sesión, token de refresco invalidado.")