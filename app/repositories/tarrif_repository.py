
from sqlalchemy.orm import Session
from models import Tarrif
from datetime import date

class TarrifRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_tariffs_for_date(self, rate_name: str, target_date: date) -> list[Tarrif]:
        """
        Obtiene las tarifas aplicables para un tipo de tarifa y una fecha específica.
        """
        return (
            self.db.query(Tarrif)
            .filter(
                Tarrif.trf_rate_name == rate_name,
                Tarrif.trf_valid_from <= target_date,
                Tarrif.trf_valid_to >= target_date,
            )
            .order_by(Tarrif.trf_lower_limit_kwh)
            .all()
        )