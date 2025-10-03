from database import Base
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, String
from sqlalchemy.orm import relationship 

class RefreshToken(Base):
    __tablename__="tbrefreshtokens"

    ref_id =         Column(Integer, primary_key=True, index=True)
    ref_user_id =    Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    ref_token =      Column(String(512), nullable=False, unique=True)
    ref_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ref_created_at = Column(TIMESTAMP(timezone=True), server_default="now()")

    user = relationship("User", back_populates="refresh_tokens")