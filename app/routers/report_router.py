# app/routers/report_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from redis import Redis

from app.database import get_db, get_redis_client
from app.core import TokenData, get_current_user
from app.schemas.monthly_report_schema import MonthlyReport, GenerateReportRequest
from app.services.report_service import generate_monthly_report

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/monthly", response_model=MonthlyReport)
def generate_monthly_report_route(
    request: GenerateReportRequest,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Genera un reporte mensual completo para el usuario autenticado.
    """
    # Validar mes
    if not 1 <= request.month <= 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El mes debe estar entre 1 y 12"
        )
    
    # Validar año razonable
    if not 2020 <= request.year <= 2030:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El año debe estar entre 2020 y 2030"
        )
    
    # Generar reporte
    report = generate_monthly_report(
        db=db,
        redis_client=redis_client,
        user_id=current_user.user_id,
        month=request.month,
        year=request.year
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo generar el reporte. Verifica que tengas dispositivos activos y datos del periodo solicitado."
        )
    
    return report


@router.get("/monthly/current", response_model=MonthlyReport)
def get_current_month_report_route(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Genera el reporte del mes actual automáticamente.
    """
    from datetime import datetime
    now = datetime.now()
    
    report = generate_monthly_report(
        db=db,
        redis_client=redis_client,
        user_id=current_user.user_id,
        month=now.month,
        year=now.year
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo generar el reporte del mes actual."
        )
    
    return report


@router.get("/monthly/available-periods")
def get_available_report_periods(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Devuelve una lista de periodos disponibles para generar reportes.
    """
    from datetime import datetime
    from app.repositories import UserRepository
    
    user_repo = UserRepository(db)
    user = user_repo.get_user_id_repository(current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Obtener fecha de creación del usuario
    user_created = user.user_created
    
    # Generar lista de periodos desde la creación hasta el mes actual
    now = datetime.now()
    periods = []
    
    # Nombres de meses en español
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    current = user_created.replace(day=1)
    while current <= now:
        periods.append({
            "month": current.month,
            "year": current.year,
            "label": f"{month_names[current.month]} {current.year}"
        })
        # Siguiente mes
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # Invertir para mostrar los más recientes primero
    periods.reverse()
    
    return {
        "available_periods": periods,
        "total_periods": len(periods)
    }
