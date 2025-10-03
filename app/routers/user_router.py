# app/routers/user_router.py (ACTUALIZADO)

from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, status, Depends

from database import get_db
from core import TokenData, get_current_user
from schemas import UserResponse, UserCreate, UserUpdate
from services import get_user_by_id_service, create_user_service, update_user_service

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint público para registrar un nuevo usuario.
    """
    user = create_user_service(db, user_data)
    if not user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo electrónico ya está en uso.")
    return user

@router.get("/me", response_model=UserResponse)
def get_current_user_route(db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    """
    Obtiene la información del usuario actualmente autenticado.
    """
    user = get_user_by_id_service(db, current_user.user_id)
    if not user:
        # Esto no debería pasar si el token es válido, pero es una buena práctica de seguridad
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return user

@router.patch("/me", response_model=UserResponse)
def update_user_route(user_data: UserUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    """
    Actualiza la información del usuario actualmente autenticado.
    """
    updated_user = update_user_service(db, current_user.user_id, user_data)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo actualizar el usuario.")
    return updated_user