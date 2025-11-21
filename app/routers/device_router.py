# app/routers/device_router.py (NUEVO)

from typing import List
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.core import TokenData, get_current_user
from app.schemas import DeviceResponse, DeviceCreate, DeviceUpdate, DeviceFCMRegister
from app.services import (
    create_device_service,
    get_all_devices_by_user_service,
    get_device_by_id_service,
    update_device_service,
    delete_device_service,
    register_fcm_token_service
)

router = APIRouter(prefix="/devices", tags=["Devices"])

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device_route(device_data: DeviceCreate, db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    device = create_device_service(db, user_id=current_user.user_id, device_data=device_data)
    if not device:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El ID de hardware ya está registrado.")
    return device

@router.get("/", response_model=List[DeviceResponse])
def get_all_devices_route(db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    return get_all_devices_by_user_service(db, user_id=current_user.user_id)

@router.get("/{dev_id}", response_model=DeviceResponse)
def get_device_by_id_route(dev_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    device = get_device_by_id_service(db, dev_id=dev_id, user_id=current_user.user_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado o no pertenece al usuario.")
    return device

@router.patch("/{dev_id}", response_model=DeviceResponse)
def update_device_route(dev_id: int, device_data: DeviceUpdate, db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    updated_device = update_device_service(db, dev_id=dev_id, user_id=current_user.user_id, device_data=device_data)
    if not updated_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado o no se pudo actualizar.")
    return updated_device

@router.delete("/{dev_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device_route(dev_id: int, db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    success = delete_device_service(db, dev_id=dev_id, user_id=current_user.user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispositivo no encontrado.")
    
