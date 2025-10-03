# app/models/user.py (ACTUALIZADO)

from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "tbusers"

    user_id =       Column(Integer, primary_key=True, index=True)
    user_name =     Column(String(100), nullable=False)
    user_email =    Column(String(150), nullable=False, unique=True)
    user_password = Column(String(255), nullable=False)
    user_trf_rate = Column(String(10), nullable=False)
    user_billing_day = Column(Integer, nullable=False, default=1)
    user_created =  Column(TIMESTAMP(timezone=True), server_default=func.now())


    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan") 
    recommendations = relationship("Recommendation", back_populates="user", cascade="all, delete-orphan") 
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan") 