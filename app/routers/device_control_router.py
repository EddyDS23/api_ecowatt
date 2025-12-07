# app/routers/device_control_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.core import TokenData, get_current_user
from app.services.device_control_service import DeviceControlService
from app.schemas.device_control_schema import ControlResponse, ControlSetRequest, StatusResponse

router = APIRouter(prefix="/control", tags=["Device Control"])

@router.post("/{device_id}/toggle", response_model=ControlResponse)
async def toggle_device_route(
    device_id: int, 
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Alterna el estado del dispositivo (ON → OFF o OFF → ON)
    
    **Ejemplo de uso:**
    ```
    POST /api/v1/control/5/toggle
    Authorization: Bearer <token>
    ```
    
    **Respuesta exitosa:**
    ```json
    {
        "success": true,
        "message": "Comando ejecutado correctamente",
        "device_name": "Cocina Principal",
        "was_on": false,
        "new_state": true,
        "action": "encendido"
    }
    ```
    
    **Errores posibles:**
    - 404: Dispositivo no encontrado
    - 403: No eres dueño del dispositivo
    - 503: MQTT desconectado o dispositivo no responde
    """
    service = DeviceControlService(db)
    result = await service.toggle_device(device_id, current_user.user_id)
    
    if not result["success"]:
        # Determinar código de error apropiado
        error_msg = result["error"]
        
        if "no encontrado" in error_msg.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "no tienes permisos" in error_msg.lower():
            status_code = status.HTTP_403_FORBIDDEN
        elif "desactivado" in error_msg.lower():
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        raise HTTPException(status_code=status_code, detail=error_msg)
    
    return ControlResponse(**result)


@router.post("/{device_id}/set", response_model=ControlResponse)
async def set_device_route(
    device_id: int,
    request: ControlSetRequest,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Fuerza el dispositivo a un estado específico
    
    **Ejemplo de uso:**
    ```
    POST /api/v1/control/5/set
    Authorization: Bearer <token>
    Content-Type: application/json
    
    {
        "state": true
    }
    ```
    
    **Respuesta exitosa:**
    ```json
    {
        "success": true,
        "message": "Comando ejecutado correctamente",
        "device_name": "Sala de Estar",
        "was_on": false,
        "new_state": true,
        "action": "encendido"
    }
    ```
    """
    service = DeviceControlService(db)
    result = await service.set_state(device_id, current_user.user_id, request.state)
    
    if not result["success"]:
        error_msg = result["error"]
        
        if "no encontrado" in error_msg.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "no tienes permisos" in error_msg.lower():
            status_code = status.HTTP_403_FORBIDDEN
        elif "desactivado" in error_msg.lower():
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        raise HTTPException(status_code=status_code, detail=error_msg)
    
    return ControlResponse(**result)


@router.get("/{device_id}/status", response_model=StatusResponse)
async def get_device_status_route(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Obtiene el estado actual completo del dispositivo
    
    **Ejemplo de uso:**
    ```
    GET /api/v1/control/5/status
    Authorization: Bearer <token>
    ```
    
    **Respuesta exitosa:**
    ```json
    {
        "success": true,
        "device_name": "Cocina Principal",
        "status": {
            "id": 0,
            "output": true,
            "apower": 1234.5,
            "voltage": 220.3,
            "current": 5.6,
            "temperature": {
                "tC": 45.2,
                "tF": 113.4
            }
        }
    }
    ```
    
    **Útil para:**
    - Verificar si el dispositivo está encendido
    - Obtener consumo actual en watts
    - Monitorear temperatura del dispositivo
    """
    service = DeviceControlService(db)
    result = await service.get_status(device_id, current_user.user_id)
    
    if not result["success"]:
        error_msg = result["error"]
        
        if "no encontrado" in error_msg.lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "no tienes permisos" in error_msg.lower():
            status_code = status.HTTP_403_FORBIDDEN
        elif "desactivado" in error_msg.lower():
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        raise HTTPException(status_code=status_code, detail=error_msg)
    
    return StatusResponse(**result)


@router.post("/{device_id}/on", response_model=ControlResponse)
async def turn_on_device_route(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atajo para encender el dispositivo (equivalente a set con state=true)
    
    **Ejemplo de uso:**
    ```
    POST /api/v1/control/5/on
    Authorization: Bearer <token>
    ```
    """
    service = DeviceControlService(db)
    result = await service.set_state(device_id, current_user.user_id, True)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result["error"]
        )
    
    return ControlResponse(**result)


@router.post("/{device_id}/off", response_model=ControlResponse)
async def turn_off_device_route(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atajo para apagar el dispositivo (equivalente a set con state=false)
    
    **Ejemplo de uso:**
    ```
    POST /api/v1/control/5/off
    Authorization: Bearer <token>
    ```
    """
    service = DeviceControlService(db)
    result = await service.set_state(device_id, current_user.user_id, False)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result["error"]
        )
    
    return ControlResponse(**result)