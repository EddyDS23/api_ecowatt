

from sqlalchemy import Column, Integer, String, DECIMAL, Date
from app.database import Base

class Tarrif(Base):
    __tablename__ = "tbtarrifs"

    trf_id =                Column(Integer, primary_key=True, autoincrement=True)
    trf_rate_name =         Column(String(10), nullable=False, index=True)
    trf_level_name =        Column(String(30), nullable=False)
    trf_lower_limit_kwh =   Column(Integer, nullable=False)
    trf_upper_limit_kwh =   Column(Integer, nullable=True)
    trf_price_per_kwh =     Column(DECIMAL(10, 5), nullable=False)
    trf_fixed_charge_mxn =  Column(DECIMAL(10, 2), default=0.00)
    trf_valid_from =        Column(Date, nullable=False, index=True)
    trf_valid_to =          Column(Date, nullable=False, index=True)