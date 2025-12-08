# app/services/ingest_service.py

from sqlalchemy.orm import Session
from redis import Redis
import json

from app.repositories import DeviceRepository, TimeSeriesRepository
from app.schemas import ShellyIngestData
from app.core import logger
from app.core.websocket_manager import manager 

DEVICE_CACHE_TTL = 3600

# 🔥 CAMBIO 1: Convertimos la función a ASYNC
async def process_shelly_data(db: Session, redis_client: Redis, data: ShellyIngestData):
    """
    Procesa los datos del Shelly y los envía al WebSocket en tiempo real.
    """
    hardware_id = data.sys_status.mac
    watts = data.switch_status.apower
    volts = data.switch_status.voltage
    amps = data.switch_status.current

    try:
        # 1. Buscar el dispositivo (con cache)
        cache_key = f"device:mac:{hardware_id}"
        cached_device = redis_client.get(cache_key)

        if cached_device:
            device_data = json.loads(cached_device)
            device_id = device_data["id"]
            user_id = device_data["user_id"]
            is_active = device_data["active"]
            # logger.debug(f"📦 Cache HIT: {hardware_id}")
        else:
            logger.info(f"🔍 Cache MISS: {hardware_id}, consultando BD")
            device_repo = DeviceRepository(db)
            device = device_repo.get_device_by_hardware_id_repository(hardware_id)
            
            if not device:
                logger.warning(f"❌ Dispositivo no registrado: {hardware_id}")
                # Guardamos "no existe" por 5 minutos para no saturar la BD
                redis_client.setex(cache_key, 300, json.dumps({"exists": False}))
                return
            
            device_data = {
                "id": device.dev_id,
                "user_id": device.dev_user_id,
                "active": device.dev_status,
                "name": device.dev_name,
                "exists": True
            }
            redis_client.setex(cache_key, DEVICE_CACHE_TTL, json.dumps(device_data))
            device_id = device.dev_id
            user_id = device.dev_user_id
            is_active = device.dev_status

        # 2. Validar estado
        if not is_active:
            # logger.debug(f"⏸️ Dispositivo inactivo: {hardware_id}")
            return
        
        # 3. Guardar en Redis TimeSeries (Operación Síncrona, pero rápida)
        ts_repo = TimeSeriesRepository(redis_client)
        ts_repo.add_measurements(
            user_id=user_id,
            device_id=device_id,
            watts=watts,
            volts=volts,
            amps=amps
        )

        # 4. ✅ ENVIAR A WEBSOCKET (NATIVO)
        # Al ser una función async, podemos usar 'await' directamente.
        # Esto asegura que el mensaje se envíe en el mismo bucle donde están los clientes.
        message_to_broadcast = {
            "watts": watts,
            "volts": volts,
            "amps": amps
        }
        
        await manager.broadcast_to_device(device_id, json.dumps(message_to_broadcast))
        
        logger.debug(f"📡 WS enviado Device {device_id}: {watts}W")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Error decodificando cache para {hardware_id}: {e}")
        redis_client.delete(cache_key)
    except Exception as e:
        logger.error(f"❌ Error procesando datos de Shelly: {e}")