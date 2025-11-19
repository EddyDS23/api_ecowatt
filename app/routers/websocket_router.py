from fastapi import WebSocket, APIRouter, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core import security, TokenData, logger, manager
from app.database import get_db
from app.database.database import SessionLocal
from app.repositories import DeviceRepository

router = APIRouter(prefix="/ws",tags=["WebSocket"])

@router.websocket("/live/{device_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    device_id: int, 
    token: str
):
   
    #  1. Validar token ANTES de aceptar el WebSocket
    try:
        token_data: TokenData = await security.get_current_user(token)
        if token_data is None:
            await websocket.close(code=1008)  # Policy Violation
            return
    except Exception as e:
        logger.warning(f"Token inválido en WebSocket: {e}")
        await websocket.close(code=1008)
        return
    
    # 2. Validar dispositivo en un scope TEMPORAL de DB (no mantenerlo abierto)
    db: Session = SessionLocal()
    try:
        device_repo = DeviceRepository(db)
        device = device_repo.get_device_by_id_repository(device_id)
        
        if not device or device.dev_user_id != token_data.user_id:
            logger.warning(
                f"Usuario {token_data.user_id} intentó acceder al WebSocket "
                f"del dispositivo {device_id} sin permisos"
            )
            await websocket.close(code=1008)
            return
        
        logger.info(
            f"WebSocket autorizado: Usuario {token_data.user_id} → "
            f"Dispositivo {device_id} ({device.dev_name})"
        )
    finally:
        # 3. CERRAR la conexión de BD inmediatamente
        db.close()
    
    #  4. Aceptar el WebSocket (DESPUÉS de validar)
    await manager.connect(device_id, websocket)
    logger.info(f"Cliente conectado al WebSocket para el dispositivo {device_id}")
    
    # 5. Loop principal del WebSocket (sin conexión a BD)
    try:
        while True:
            # Mantener la conexión abierta esperando mensajes
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(device_id, websocket)
        logger.info(f"Cliente desconectado del WebSocket para el dispositivo {device_id}")
