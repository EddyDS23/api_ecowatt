from sqlalchemy.orm import Session


from models import Device
from repositories import DeviceRepository
from schemas import DeviceCreate, DeviceUpdate, DeviceResponse

from core import logger

def get_device_by_id_service(db:Session, dev_id:int) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    
    device = device_repo.get_device_by_id_repository(dev_id)

    if device:
        logger.info("Dispositivo encontrado")
        return DeviceResponse.model_validate(device)
    logger.info("Dispositivo no encontrado")
    return None

def get_all_device_by_user_service(db:Session, user_id:int) -> list[DeviceResponse]:
    device_repo = DeviceRepository(db)
    devices = device_repo.get_all_device_by_user_repository(user_id)
    logger.info("Dispositivos obtenidos o no obtenidos")
    return [DeviceResponse.model_validate(device) for device in devices]


def create_device_service(db:Session, user_id:int, device_data:DeviceCreate) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    new_device = Device(**device_data.model_dump())
    new_device.dev_user_id = user_id
    device = device_repo.create_device_repository(new_device)
    if device:
        logger.info("Dispositivo creado/agregado exitosamente")
        return DeviceResponse.model_validate(device)
    logger.error("Dispositivo no creado")
    return None


def update_device_service(db:Session, dev_id:int, device_data:DeviceUpdate) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    device = device_repo.update_device_repository(dev_id,**device_data.model_dump(exclude_unset=True))
    if device:
        logger.info("Dispositivo actualizado exitosamente")
        return DeviceResponse.model_validate(device)
    logger.error("Dispositivo no actualizado")
    return None

def change_status_device_service(db:Session, dev_id:int) -> DeviceResponse | None:
    device_repo = DeviceRepository(db)
    device = device_repo.change_device_status(dev_id)
    if device:
        logger.info("Se ah cambiado el estado de el dispositivo")
        return DeviceResponse.model_validate(device)
    logger.error("No se pudo cambiar el estado del dispositivo")    


def delete_device_service(db:Session, dev_id:int) -> bool | None:
    device_repo = DeviceRepository(db)
    answer = device_repo.delete_device_repository(dev_id)
    if answer:
        logger.info("Se ah eliminado el dispositivo")
        return answer
    logger.error("No se pudo eliminar el dispositivo")
    return None


    

