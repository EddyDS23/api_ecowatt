
from models import Report
from sqlalchemy.orm import Session

from core import logger


class ReportRepository:

    def __init__(self,db:Session):
        self.db = db


    def get_report_by_id_repository(self,rep_id:int) -> Report | None:
        return self.db.query(Report).filter(Report.rep_id == rep_id).first()
    
    def get_all_report_by_user_repository(self,user_id:int) -> list[Report]:
        return  self.db.query(Report).filter(Report.rep_user_id == user_id).all()
    

    def create_report_repository(self,new_report:Report) -> Report | None:

        try:

            self.db.add(new_report)
            self.db.commit()
            self.db.refresh(new_report)
            logger.info("Reporte creado exitosamente")
            return new_report
        except Exception as e:
            logger.error(f"No se pudo crear el reporte: {e}")
            self.db.rollback()
            return None
        

    def update_report_repository(self,rep_id:int,update_data:dict) -> Report | None:

        try:

            report = self.get_report_by_id_repository(rep_id)

            if not report:
                logger.info(f"No se encontro reporte ningun reporte con el id {rep_id}")

            report.rep_total_kwh = update_data.get("rep_total_kwh",report.rep_total_kwh)
            report.rep_estimated_cost = update_data.get("rep_estimated_cost",report.rep_estimated_cost)

            self.db.commit()
            self.db.refresh(report)
            logger.info(f"Se actualizo el report con id {rep_id}")
            return report
        except Exception as e:
            logger.error(f"No se pudo actualizar el reporte con id {rep_id}: {e}")
            self.db.rollback()
            return None
        

    def delete_report_repository(self,rep_id:int) -> bool | None:
        
        try:
            report = self.get_report_by_id_repository(rep_id)

            if not report:
                logger.info(f"No se encontro reporte ningun reporte con el id {rep_id}")

            self.db.delete(report)
            self.db.commit()
            logger.info(f"Se elimino correctamente el reporte con id {rep_id}")
            return True
        except Exception as e:
            logger.error(f"No se eliminar el reporte con id {rep_id}: {e}")