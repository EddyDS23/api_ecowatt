from database import Base

from sqlalchemy import Column, String, Integer, TIMESTAMP, Boolean, ForeignKey,Text
from sqlalchemy.sql import func, expression
from sqlalchemy.orm import relationship 

class Device(Base):
    __tablename__="tbdevice"

    dev_id =            Column(Integer, primary_key=True, index=True)
    dev_user_id =       Column(Integer, ForeignKey("tbusers.user_id"),ondelete="CASCADE",nullable=False)
    dev_brand =         Column(String(200),nullable=False)
    dev_model =         Column(String(200),nullable=False)
    dev_endpoint_url =  Column(Text,nullable=False)
    dev_installed =     Column(TIMESTAMP(timezone=True),server_default=func.now())
    dev_status =        Column(Boolean, server_default=expression.true)

    user = relationship("User",back_populates="devices")