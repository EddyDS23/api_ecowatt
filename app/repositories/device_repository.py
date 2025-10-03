
from models import Device
from sqlalchemy.orm import Session

from core import logger

class DeviceRepository:

    def __init__(self, db:Session):
        self.db = db

    
    def get_device_by_id_repository(self,dev_id:int) -> Device | None:
        return self.db.query(Device).filter(Device.dev_id == dev_id).first()
    
    def get_all_device_by_user_repository(self,user_id:int) -> list[Device]:
        return self.db.query(Device).filter(Device.dev_user_id == user_id).all()


    def create_device_repository(self,new_device:Device) -> Device | None:

        try:
            self.db.add(new_device)
            self.db.commit()
            self.db.refresh(new_device)
            logger.info("Dispositivo creado exitosamente")
            return new_device
        except Exception as e:
            logger.error(f"No se pudo agregar el dispositivo: {e}")
            self.db.rollback()
            return None

    
    def update_device_repository(self, dev_id:int, update_data:dict) -> Device | None:
        
        try:

            device = self.get_device_by_id_repository(dev_id)

            if not device:
                logger.info(f"No se encontro dispositivo con id {dev_id}")
                return None
            
            for key, value in update_data.items():
                setattr(device, key, value)
            
            self.db.commit()
            self.db.refresh(device)
            return device
        except Exception as e:
            logger.error(f"No se pudo actualizar el dispositivo con id {dev_id}: {e}")
            self.db.rollback()
            return None
        

    def change_device_status(self, dev_id: int) -> Device | None:
        try:
            device = self.get_device_by_id_repository(dev_id)

            if not device:
                logger.info(f"No se encontró dispositivo con id {dev_id}")
                return None
            
            device.dev_status = not device.dev_status
            self.db.commit()
            self.db.refresh(device)
            logger.info(f"Estado del dispositivo {dev_id} actualizado a {device.dev_status}")
            return device
        
        except Exception as e:
            logger.error(f"No se pudo actualizar el estado del dispositivo {dev_id}: {e}")
            self.db.rollback()
            return None

        
    def delete_device_repository(self,dev_id:int) -> bool | False:

        try:

            device = self.get_device_by_id_repository(dev_id)

            if not device:
                logger.info(f"No se encontro dispositivo con id {dev_id}")
                return False
            

            self.db.delete(device)
            self.db.commit()
            logger.info(f"Se elimino al dispositvo con id {dev_id}")
            return True
        except Exception as e:
            logger.error(f"No se pudo eliminar el dispositivo con id {dev_id}: {e}")
            self.db.rollback()
            return False
