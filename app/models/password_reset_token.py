
from app.database import Base
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, String
from sqlalchemy.sql import func

class PasswordResetToken(Base):
    __tablename__ = "tbpasswordresettokens"

    prt_id = Column(Integer, primary_key=True, index=True)
    prt_user_id = Column(Integer, ForeignKey("tbusers.user_id", ondelete="CASCADE"), nullable=False)
    prt_token = Column(String(255), nullable=False, unique=True)
    prt_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    prt_created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())