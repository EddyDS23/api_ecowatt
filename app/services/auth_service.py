

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from datetime import datetime, timedelta, timezone
import secrets


from app.repositories import UserRepository, RefreshTokenRepository, PasswordResetRepository
from app.schemas import UserLogin, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.core import logger, settings, security

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


conf = ConnectionConfig(
    MAIL_USERNAME = settings.MAIL_USERNAME,
    MAIL_PASSWORD = settings.MAIL_PASSWORD,
    MAIL_FROM = settings.MAIL_FROM,
    MAIL_PORT = settings.MAIL_PORT,
    MAIL_SERVER = settings.MAIL_SERVER,
    MAIL_STARTTLS = settings.MAIL_STARTTLS,
    MAIL_SSL_TLS = settings.MAIL_SSL_TLS,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

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


async def request_password_reset(db: Session, request: ForgotPasswordRequest):
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_email_repository(request.user_email)

    if not user:
        logger.warning(f"Solicitud de reseteo para email no existente: {request.user_email}")
        # Por seguridad, no revelamos si un email existe. La respuesta siempre es la misma.
        return {"message": "Si tu correo está registrado, recibirás un email con instrucciones."}

    # Generar y guardar el token de reseteo
    reset_repo = PasswordResetRepository(db)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1) # El token es válido por 1 hora
    reset_repo.create_token(user_id=user.user_id, token=token, expires_at=expires_at)

    # Preparar y enviar el correo
    message = MessageSchema(
        subject="Restablecimiento de Contraseña - EcoWatt",
        recipients=[user.user_email],
        body=f"Hola {user.user_name},\n\nHas solicitado restablecer tu contraseña. Usa el siguiente token para completar el proceso en la aplicación: \n\nToken: {token}\n\nEste token expirará en 1 hora.\n\nSi no solicitaste esto, por favor ignora este correo.",
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)
    logger.info(f"Correo de reseteo de contraseña enviado a {user.user_email}")
    return {"message": "Si tu correo está registrado, recibirás un email con instrucciones."}


def reset_password(db: Session, request: ResetPasswordRequest):
    reset_repo = PasswordResetRepository(db)
    reset_token_obj = reset_repo.get_token(request.token)

    # Validar el token
    if not reset_token_obj or reset_token_obj.prt_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El token es inválido o ha expirado.")

    # Actualizar la contraseña del usuario
    user_repo = UserRepository(db)
    new_hashed_password = pwd_context.hash(request.new_password)
    success = user_repo.change_password_user_repository(reset_token_obj.prt_user_id, new_hashed_password)

    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo actualizar la contraseña.")

    # Eliminar el token una vez que ha sido usado
    reset_repo.delete_token(reset_token_obj.prt_id)

    logger.info(f"Contraseña restablecida para el usuario ID {reset_token_obj.prt_user_id}")
    return {"message": "Contraseña actualizada exitosamente."}