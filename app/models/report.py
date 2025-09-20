from sqlalchemy import Column, Integer, NUMERIC, ForeignKey,TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base

class Report(Base):
    __tablename__ = "tbreports"

    rep_id = Column(Integer, primary_key=True, index=True)
    rep_user_id = Column(Integer, ForeignKey("tbusers.user_id"),nullable=False)
    rep_total_kwh = Column(NUMERIC(10,2),nullable=False)
    rep_estimated_cost = Column(NUMERIC(10,2),nullable=False)
    rep_created = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User",back_populates="reports")