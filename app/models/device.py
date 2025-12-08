# app/models/device.py (ACTUALIZADO)

from app.database import Base
from sqlalchemy import Column, String, Integer, TIMESTAMP, Boolean, ForeignKey
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import relationship 

class Device(Base): 
    __tablename__="tbdevice"

    dev_id =            Column(Integer, primary_key=True, index=True)
    dev_user_id =       Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    dev_hardware_id =   Column(String(255), nullable=False, unique=True) 
    dev_name =          Column(String(100), nullable=False) 
    dev_brand =         Column(String(200), default='Shelly')
    dev_model =         Column(String(200), default='1PM Gen4')
    dev_mqtt_prefix =   Column(String(50),default='shellyplus1pm')
    dev_installed =     Column(TIMESTAMP(timezone=True), server_default=func.now())
    dev_status =        Column(Boolean, server_default=expression.true())

    user = relationship("User", back_populates="devices")