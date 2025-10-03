
from sqlalchemy import Column, Integer, DECIMAL, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Report(Base):
    __tablename__ = "tbreports"

    rep_id = Column(Integer, primary_key=True, index=True)
    rep_user_id = Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False) 
    rep_total_kwh = Column(DECIMAL(10, 2), nullable=False)
    rep_estimated_cost = Column(DECIMAL(10, 2), nullable=False)
    rep_created = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reports")