from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "tbusers"

    user_id =       Column(Integer,primary_key=True, index=True)
    user_name =     Column(String(100),nullable=False)
    user_email =    Column(String(150), nullable=False)
    user_password = Column(String(255), nullable=False)
    user_created =  Column(TIMESTAMP(timezone=True),server_default=func.now())

    devices = relationship("Device", back_populates="user")
    reports = relationship("Report",back_populates="user")
