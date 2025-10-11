# app/services/ingest_service.py

from sqlalchemy.orm import Session
from redis import Redis
from app.repositories import DeviceRepository, TimeSeriesRepository
from app.schemas import ShellyIngestData
from app.core import logger

def process_shelly_data(db: Session, redis_client: Redis, data: ShellyIngestData):
    """
    Procesa los datos recibidos de un dispositivo Shelly, incluyendo potencia, voltaje y amperaje.
    """
    hardware_id = data.sys_status.mac

    # Extraer los tres valores del schema
    watts = data.switch_status.apower
    volts = data.switch_status.voltage
    amps = data.switch_status.current

    # 1. Buscar el dispositivo en PostgreSQL (sin cambios)
    device_repo = DeviceRepository(db)
    device = device_repo.get_device_by_hardware_id_repository(hardware_id)

    if not device or not device.dev_status:
        status = "no registrado" if not device else "inactivo"
        logger.warning(f"Datos recibidos de un dispositivo {status}: {hardware_id}")
        return

    # 2. Guardar las tres mediciones en Redis
    ts_repo = TimeSeriesRepository(redis_client)
    ts_repo.add_measurements(
        user_id=device.dev_user_id,
        device_id=device.dev_id,
        watts=watts,
        volts=volts,
        amps=amps
    )

    # (Aquí es donde, en el futuro, también enviaremos los datos por WebSocket)