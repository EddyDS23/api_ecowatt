from sqlalchemy import Column, Integer, String, DECIMAL

from database import Base


class Tarrif(Base):
    __tablename__ = "tbtarrifs"

    trf_id = Column(Integer, primary_key=True, autoincrement=True)
    trf_rate = Column(String(10), nullable=False)
    trf_month = Column(Integer, nullable=False)
    trf_type = Column(String(20), nullable=False)
    trf_limit = Column(Integer, nullable=False)
    trf_price = Column(DECIMAL(10,3), nullable=False)
