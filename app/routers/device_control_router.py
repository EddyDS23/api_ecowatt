# app/routers/device_control_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.core import TokenData, get_current_user
from app.services.device_control_service import DeviceControlService

router = APIRouter(prefix="/control", tags=["Device Control"])

# Modelo simple para recibir el estado deseado
class ControlRequest(BaseModel):
    state: bool # True = ON, False = OFF

@router.post("/{device_id}/toggle")
async def toggle_device_route(
    device_id: int, 
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Alterna el estado del dispositivo (Switch.Toggle)"""
    service = DeviceControlService(db)
    result = await service.toggle_device(device_id, current_user.user_id)
    
    if not result["success"]:
        # Si falla MQTT (Mosquitto caído), devolvemos error 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=result["error"]
        )
    
    return result

@router.post("/{device_id}/set")
async def set_device_route(
    device_id: int,
    request: ControlRequest,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Fuerza el encendido o apagado (Switch.Set)"""
    service = DeviceControlService(db)
    result = await service.set_state(device_id, current_user.user_id, request.state)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=result["error"]
        )
    
    return result