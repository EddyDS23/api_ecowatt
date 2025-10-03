from app.database import Base
from sqlalchemy import Column, Integer, TIMESTAMP, Boolean, ForeignKey, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship 

class Alert(Base):
    __tablename__="tbalerts"

    ale_id =         Column(Integer, primary_key=True, index=True)
    ale_user_id =    Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    ale_title =      Column(String(150), nullable=False)
    ale_body =       Column(Text, nullable=False)
    ale_is_read =    Column(Boolean, server_default="false")
    ale_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="alerts")