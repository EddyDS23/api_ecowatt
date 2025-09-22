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
        logger.info("Usuario verificada exitosamente ")
        return UserResponse.model_validate(user)
    logger.error("autenticacion de usuario fallida ")
    return None


def create_user_service(db:Session, user_data:UserCreate) -> UserResponse | None:
    user_data.user_password = pwd_context.hash(user_data.user_password)
    new_user = User(**user_data.model_dump())

    user_repo = UserRepository(db)
    user = user_repo.create_user_repository(new_user)
    if user:
        logger.info("Usuario creado exitosamente")
        return UserResponse.model_validate(user)
    logger.error("Usuario no creado")
    return None

def update_user_service(db:Session,user_id:int,user_data:UserUpdate) -> UserResponse | None:
    user_repo = UserRepository(db)
    user = user_repo.update_user_repository(user_id, user_data.model_dump(exclude_unset=True))
    if user:
        logger.info("Usuario actualizado exitosamente")
        return UserResponse.model_validate(user)
    logger.error("Usuario no pudo actualizarse")
    return None


def change_password_user_service(db:Session,user_id:int,user_data:UserChangePassword) -> bool | None:
    
    password_hashed = pwd_context.hash(user_data.user_password)
    
    user_repo = UserRepository(db)
    answer = user_repo.change_password_user_repository(user_id,password_hashed)
    if answer:
        logger.info("Contraseña cambiada exisitosamente")
        return answer
    logger.error("Contraseña no cambiada")
    return None



