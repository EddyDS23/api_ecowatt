from fastapi import WebSocket, APIRouter, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core import security, TokenData, logger, manager
from app.database import get_db
from app.repositories import DeviceRepository

router = APIRouter(prefix="/ws",tags=["WebSocket"])

@router.websocket("/live/{device_id}")
async def websocket_endpoint(websocket:WebSocket, device_id:int, token:str, db:Session = Depends(get_db)):
    
    try:
        token_data:TokenData = await security.get_current_user(token)

        if token_data is None:
            await websocket.close(code=1008)
            return
    except Exception:
        await websocket.close(code=1008)
        return
    
    device_repo = DeviceRepository(db)
    device = device_repo.get_device_by_id_repository(device_id)
    if not device or device.dev_user_id != token_data.user_id:
        logger.warning(f"Usuario {token.user_id} intento acceder al webSocket del dispositivo {device_id} sin permisos")
        await websocket.close(code=1008)
        return
    
    await manager.connect(device_id,websocket)
    logger.info(f"Cliente conectado al WebSocket para el dispositivo {device_id}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(device_id, websocket)
        logger.info(f"Cliente desconectado del WebSocket para el dispositivo {device_id}")
