from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import Report
from app.core import logger
from datetime import datetime, timezone, timedelta
from typing import Optional, List

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_month(self, user_id: int, month: int, year: int) -> Optional[Report]:
        """Obtiene reporte guardado de un mes específico (no expirado)"""
        return (
            self.db.query(Report)
            .filter(
                and_(
                    Report.mr_user_id == user_id,
                    Report.mr_month == month,
                    Report.mr_year == year,
                    Report.mr_expires_at > datetime.now(timezone.utc)
                )
            )
            .first()
        )

    def get_all_by_user(self, user_id: int) -> List[Report]:
        """Obtiene todos los reportes no expirados de un usuario"""
        return (
            self.db.query(Report)
            .filter(
                and_(
                    Report.mr_user_id == user_id,
                    Report.mr_expires_at > datetime.now(timezone.utc)
                )
            )
            .order_by(Report.mr_year.desc(), Report.mr_month.desc())
            .all()
        )

    def save(
        self, 
        user_id: int, 
        month: int, 
        year: int, 
        report_data: dict, 
        total_kwh: float, 
        total_cost: float
    ) -> bool:
        """Guarda reporte con expiración de 1 año"""
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
            
            # Buscar si existe (sin filtro de expiración)
            existing = (
                self.db.query(Report)
                .filter(
                    and_(
                        Report.mr_user_id == user_id,
                        Report.mr_month == month,
                        Report.mr_year == year
                    )
                )
                .first()
            )
            
            if existing:
                # Actualizar
                existing.mr_report_data = report_data
                existing.mr_total_kwh = total_kwh
                existing.mr_total_cost = total_cost
                existing.mr_generated_at = datetime.now(timezone.utc)
                existing.mr_expires_at = expires_at
                logger.info(f"Reporte actualizado: user={user_id}, {month}/{year}")
            else:
                # Crear nuevo
                new_report = Report(
                    mr_user_id=user_id,
                    mr_month=month,
                    mr_year=year,
                    mr_report_data=report_data,
                    mr_total_kwh=total_kwh,
                    mr_total_cost=total_cost,
                    mr_expires_at=expires_at
                )
                self.db.add(new_report)
                logger.info(f"Reporte creado: user={user_id}, {month}/{year}")
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error guardando reporte: {e}")
            self.db.rollback()
            return False

    def delete_expired(self) -> int:
        """Elimina reportes expirados (> 1 año)"""
        try:
            result = (
                self.db.query(Report)
                .filter(Report.mr_expires_at < datetime.now(timezone.utc))
                .delete()
            )
            self.db.commit()
            logger.info(f"🧹 {result} reportes expirados eliminados")
            return result
        except Exception as e:
            logger.error(f"Error eliminando reportes: {e}")
            self.db.rollback()
            return 0