# app/services/device_service.py (ACTUALIZADO)

from sqlalchemy.orm import Session
from app.models import Device
from app.repositories import DeviceRepository
from app.schemas import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceFCMRegister
from app.core import logger

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


def register_fcm_token_service(db: Session, dev_id: int, user_id: int, dev_fcm_data: DeviceFCMRegister) -> bool:
    """
    Registra o actualiza el token FCM para un dispositivo específico del usuario.
    """
    device_repo = DeviceRepository(db)
    device_to_update = device_repo.get_device_by_id_repository(dev_id)

    # Verificar si el dispositivo existe y pertenece al usuario
    if not device_to_update or device_to_update.dev_user_id != user_id:
        logger.warning(
            f"Usuario {user_id} intentó registrar token FCM para dispositivo {dev_id} "
            "no autorizado o inexistente."
        )
        return False

    # Actualizar el token
    updated_device = device_repo.update_device_repository(
        dev_id, 
        {"dev_fcm_token": dev_fcm_data.fcm_token}
    )

    if updated_device:
        logger.info(
            f"✅ Token FCM actualizado para dispositivo {dev_id} del usuario {user_id}. "
            f"Token: {dev_fcm_data.fcm_token[:20]}...{dev_fcm_data.fcm_token[-10:]}"
        )
        return True
    else:
        logger.error(f"❌ No se pudo actualizar el token FCM para dispositivo {dev_id}.")
        return False