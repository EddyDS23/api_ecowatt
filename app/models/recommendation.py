from app.database import Base
from sqlalchemy import Column, Integer, TIMESTAMP, Boolean, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship 

class Recommendation(Base):
    __tablename__="tbrecommendations"

    rec_id =         Column(Integer, primary_key=True, index=True)
    rec_user_id =    Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    rec_text =       Column(Text, nullable=False)
    rec_is_read =    Column(Boolean, server_default="false")
    rec_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="recommendations")