# app/services/user_service.py (ACTUALIZADO)

from sqlalchemy.orm import Session
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserResponse, UserCreate, UserUpdate
from passlib.context import CryptContext
from app.core import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_id_service(db: Session, user_id: int) -> UserResponse | None:
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(user_id)
    if user:
        return UserResponse.model_validate(user)
    return None

def create_user_service(db: Session, user_data: UserCreate) -> UserResponse | None:
    user_repo = UserRepository(db)
    existing_user = user_repo.get_user_by_email_repository(user_data.user_email)
    if existing_user:
        logger.warning(f"Intento de crear usuario con email duplicado: {user_data.user_email}")
        return None

    hashed_password = pwd_context.hash(user_data.user_password)
    user_data_dict = user_data.model_dump()
    user_data_dict['user_password'] = hashed_password
    
    new_user = User(**user_data_dict)

    user = user_repo.create_user_repository(new_user)
    if user:
        logger.info("Usuario creado exitosamente en servicio")
        return UserResponse.model_validate(user)
    
    logger.error("Usuario no creado en servicio")
    return None

def update_user_service(db: Session, user_id: int, user_data: UserUpdate) -> UserResponse | None:
    user_repo = UserRepository(db)
    update_data = user_data.model_dump(exclude_unset=True) 
    
    if not update_data:
        logger.info(f"No hay datos para actualizar para el usuario {user_id}")
        user = user_repo.get_user_id_repository(user_id)
        return UserResponse.model_validate(user) if user else None

    if "user_email" in update_data:
        existing_user = user_repo.get_user_by_email_repository(update_data["user_email"])
        if existing_user and existing_user.user_id != user_id:
            logger.warning(f"Intento de actualizar a un email duplicado: {update_data['user_email']}")
            return None

    user = user_repo.update_user_repository(user_id, update_data)
    if user:
        logger.info("Usuario actualizado exitosamente en servicio")
        return UserResponse.model_validate(user)
    
    logger.error("Usuario no pudo actualizarse en servicio")
    return None