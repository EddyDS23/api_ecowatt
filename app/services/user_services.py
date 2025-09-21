from sqlalchemy.orm import Session

from models import User
from repositories import UserRepository
from schemas import UserResponse, UserCreate, UserUpdate, UserChangePassword, UserLogin

from passlib.context import CryptContext

from core import logger

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

def get_user_service(db:Session, user_id:int) -> UserResponse | None:
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if user:
        logger.info("Usuario regresado correctamente")
        return UserResponse.model_validate(user)
    logger.info("No se regreso ningun usuario")
    return None

def authenticate_user_service(db:Session, user_data:UserLogin) -> UserResponse | None:
    user_repo=UserRepository(db)
    user = user_repo.get_user_by_email_repository(user_data.user_email)
    if user and pwd_context.verify(user_data.user_password,user.user_password):
        logger.info("Usuario verificada ")
        return UserResponse.model_validate(user)
        