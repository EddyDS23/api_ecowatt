from app.models import User
from sqlalchemy.orm import Session

from app.core import logger

class UserRepository:

    def __init__(self,db:Session):
        self.db = db

    def get_user_id_repository(self,user_id:int)-> User | None:
        return self.db.query(User).filter(User.user_id == user_id).first()
    
    def get_user_by_email_repository(self,user_email:str) -> User | None:
        return self.db.query(User).filter(User.user_email == user_email).first()
    
    def create_user_repository(self,new_user:User)-> User|None:
        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            logger.info("Usuario creado exitosamente")
            return new_user
        except Exception as e:
            logger.error(f"Cliente no creado en repository : {e}")
            self.db.rollback()
            return None
        
    def update_user_repository(self,user_id:int, update_data:dict) -> User | None:

        try:
            user = self.get_user_id_repository(user_id)

            if not user:
                logger.debug(f"No se encontro usuario con el id {user_id}")
                return None
            
            for key, value in update_data.items():
                setattr(user, key, value)

            self.db.commit()
            self.db.refresh(user)
            logger.info("Usuario actualizado exitosamente")
            return user
        except Exception as e:
            logger.error(f"Usuario no actualizado con id {user_id}: {e}")
            self.db.rollback()
            return None
        


    def change_password_user_repository(self,user_id:int,password_hashed:str)-> bool | None:
        
        try:
            user = self.get_user_id_repository(user_id)

            if not user:
                logger.debug(f"No se encontro usuario con el id {user_id}")
                return None
            
            user.user_password = password_hashed

            self.db.commit()
            self.db.refresh(user)
            logger.info("Contraseña actualizada exitosamente")
            return True
        except Exception as e:
            logger.error(f"Contraseña no actualizado: {e}")
            self.db.rollback()
            return False
        

