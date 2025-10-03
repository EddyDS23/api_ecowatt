# app/services/device_service.py (ACTUALIZADO)

from sqlalchemy.orm import Session
from models import Device
from repositories import DeviceRepository
from schemas import DeviceCreate, DeviceUpdate, DeviceResponse
from core import logger

def get_device_by_id_service(db: Session, dev_id: int, user_id: int) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    device = device_repo.get_device_by_id_repository(dev_id)

    # ¡Importante! Asegurarse de que el dispositivo pertenece al usuario que hace la petición.
    if device and device.dev_user_id == user_id:
        return DeviceResponse.model_validate(device)
    
    logger.warning(f"Usuario {user_id} intentó acceder al dispositivo {dev_id} sin permiso.")
    return None

def get_all_devices_by_user_service(db: Session, user_id: int) -> list[DeviceResponse]:
    device_repo = DeviceRepository(db)
    devices = device_repo.get_all_device_by_user_repository(user_id)
    return [DeviceResponse.model_validate(device) for device in devices]

def create_device_service(db: Session, user_id: int, device_data: DeviceCreate) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)

    # Validar que el hardware_id (MAC del Shelly) no esté ya registrado
    existing_device = device_repo.get_device_by_hardware_id_repository(device_data.dev_hardware_id)
    if existing_device:
        logger.warning(f"Intento de registrar hardware_id duplicado: {device_data.dev_hardware_id}")
        return None

    new_device_data = device_data.model_dump()
    new_device_data['dev_user_id'] = user_id
    
    new_device = Device(**new_device_data)
    
    device = device_repo.create_device_repository(new_device)
    if device:
        logger.info(f"Dispositivo creado para el usuario {user_id}")
        return DeviceResponse.model_validate(device)
    
    return None

def update_device_service(db: Session, dev_id: int, user_id: int, device_data: DeviceUpdate) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    device_to_update = device_repo.get_device_by_id_repository(dev_id)
    
    if not device_to_update or device_to_update.dev_user_id != user_id:
        return None # No se encontró o no pertenece al usuario

    update_data = device_data.model_dump(exclude_unset=True)
    if not update_data:
        return DeviceResponse.model_validate(device_to_update)

    updated_device = device_repo.update_device_repository(dev_id, update_data)
    
    if updated_device:
        return DeviceResponse.model_validate(updated_device)
    
    return None

def delete_device_service(db: Session, dev_id: int, user_id: int) -> bool:
    device_repo = DeviceRepository(db)
    device = device_repo.get_device_by_id_repository(dev_id)
    
    if not device or device.dev_user_id != user_id:
        return False # No se encontró o no pertenece al usuario
        
    return device_repo.delete_device_repository(dev_id)