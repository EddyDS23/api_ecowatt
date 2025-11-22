from sqlalchemy import Column, Integer, DECIMAL, ForeignKey, TIMESTAMP, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Report(Base):
    __tablename__ = "tbmonthlyreports"

    mr_id = Column(Integer, primary_key=True, index=True)
    mr_user_id = Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    mr_month = Column(Integer, nullable=False)
    mr_year = Column(Integer, nullable=False)
    
    mr_report_data = Column(JSONB, nullable=False)
    mr_total_kwh = Column(DECIMAL(10, 2))
    mr_total_cost = Column(DECIMAL(10, 2))
    
    mr_generated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    mr_expires_at = Column(TIMESTAMP(timezone=True))

    user = relationship("User", back_populates="reports")
    
    __table_args__ = (
        CheckConstraint('mr_month >= 1 AND mr_month <= 12', name='check_month'),
        CheckConstraint('mr_year >= 2020 AND mr_year <= 2100', name='check_year'),
    )