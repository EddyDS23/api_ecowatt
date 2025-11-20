from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class FCMToken(Base):
    __tablename__ = "tbfcmtokens"

    fcm_id = Column(Integer, primary_key=True)
    fcm_user_id = Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    fcm_token = Column(String(255), nullable=False, unique=True)
    fcm_device_name = Column(String(100))
    fcm_platform = Column(String(20))
    fcm_last_used = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="fcm_tokens")