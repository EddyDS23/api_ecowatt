

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from sib_api_v3_sdk.rest import ApiException
import secrets
import sib_api_v3_sdk


from app.repositories import UserRepository, RefreshTokenRepository, PasswordResetRepository
from app.schemas import UserLogin, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.core import logger, settings, security

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
REFRESH_TOKEN_DAYS = 30

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

    # 2. Crear Refresh Token de larga duración (30 días)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_DAYS)
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
    """
    1. Valida el refresh token actual
    2. Genera un nuevo access token
    3. Genera un NUEVO refresh token (rotación)
    4. Invalida el refresh token anterior
    5. Devuelve ambos tokens nuevos
    """
    token_repo = RefreshTokenRepository(db)
    old_refresh_token = token_repo.get_token(refresh_token_str)

    # Validar que el token de refresco exista y no haya expirado
    if not old_refresh_token or old_refresh_token.ref_expires_at < datetime.now(timezone.utc):
        logger.warning(f"Intento de uso de refresh token inválido o expirado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = old_refresh_token.ref_user_id

    # 1. Generar un nuevo access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = security.create_token(
        data={"user_id": user_id}, expires_delta=access_token_expires
    )
    
    # 2. ROTACIÓN: Generar un NUEVO refresh token con 30 días de vida
    new_refresh_token_str = secrets.token_urlsafe(32)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_DAYS)
    expires_at = datetime.now(timezone.utc) + refresh_token_expires
    
    # 3. Guardar el nuevo refresh token
    token_repo.create_token(
        user_id=user_id, 
        token=new_refresh_token_str, 
        expires_at=expires_at
    )
    
    # 4. Eliminar el refresh token anterior (invalidarlo)
    token_repo.delete_token(refresh_token_str)
    
    logger.info(f"Refresh token rotado exitosamente para usuario {user_id}")
    
    # 5. Devolver AMBOS tokens nuevos
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token_str,  # ¡Token nuevo!
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
        return {"message": "Si tu correo está registrado, recibirás un email con instrucciones."}

    # La lógica para generar y guardar el token no cambia
    reset_repo = PasswordResetRepository(db)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    reset_repo.create_token(user_id=user.user_id, token=token, expires_at=expires_at)

    # --- Lógica de envío de correo con la API de Brevo ---
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = settings.BREVO_API_KEY

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    subject = "Restablecimiento de Contraseña - EcoWatt"
    html_content = f"<html><body><p>Hola {user.user_name},</p><p>Has solicitado restablecer tu contraseña. Usa el siguiente token para completar el proceso en la aplicación:</p><h3>Token: {token}</h3><p>Este token expirará en 1 hora.</p><p>Si no solicitaste esto, por favor ignora este correo.</p></body></html>"
    sender = {"name": "EcoWatt App", "email": settings.BREVO_SENDER_EMAIL}
    to = [{"email": user.user_email, "name": user.user_name}]

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Correo de reseteo enviado a {user.user_email} via API. Message ID: {api_response.message_id}")
    except ApiException as e:
        logger.error(f"Error al enviar correo via API de Brevo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo enviar el correo de recuperación.")

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