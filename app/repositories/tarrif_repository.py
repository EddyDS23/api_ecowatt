from sqlalchemy.orm import Session
from models import Tarrif

class TarrifRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_tramos_by_rate_and_month(self, trf_rate: str, month: int):
        return self.db.query(Tarrif).filter(Tarrif.trf_rate == trf_rate, Tarrif.trf_month == month).order_by(Tarrif.trf_limit).all()
