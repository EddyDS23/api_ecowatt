# app/services/ingest_service.py (VERSIÓN CORREGIDA)

from sqlalchemy.orm import Session
from redis import Redis
import json

from app.repositories import DeviceRepository, TimeSeriesRepository
from app.schemas import ShellyIngestData
from app.core import logger
from app.core.websocket_manager import manager # Importamos el gestor de WebSockets

# Hacemos la función asíncrona para poder usar 'await' al enviar el mensaje
async def process_shelly_data(db: Session, redis_client: Redis, data: ShellyIngestData):
    hardware_id = data.sys_status.mac
    watts = data.switch_status.apower
    volts = data.switch_status.voltage
    amps = data.switch_status.current

    # 1. Buscar el dispositivo en PostgreSQL
    device_repo = DeviceRepository(db)
    device = device_repo.get_device_by_hardware_id_repository(hardware_id)

    if not device or not device.dev_status:
        status = "no registrado" if not device else "inactivo"
        logger.warning(f"Datos recibidos de un dispositivo {status}: {hardware_id}")
        return

    # 2. Guardar las mediciones en Redis
    ts_repo = TimeSeriesRepository(redis_client)
    ts_repo.add_measurements(
        user_id=device.dev_user_id,
        device_id=device.dev_id,
        watts=watts,
        volts=volts,
        amps=amps
    )

    # 3. Preparar y enviar los datos a través del WebSocket
    message_to_broadcast = {
        "watts": watts,
        "volts": volts,
        "amps": amps
    }
    await manager.broadcast_to_device(device.dev_id, json.dumps(message_to_broadcast))