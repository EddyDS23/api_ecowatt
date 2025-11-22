# app/routers/report_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel

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
    
    ✅ NUEVO COMPORTAMIENTO:
    - Mes actual: Genera en tiempo real desde Redis (no guarda en BD)
    - Mes anterior: Busca en BD primero, si no existe lo genera y guarda
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
    
    # Generar reporte (ahora con lógica de cache)
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
    Siempre genera en tiempo real (no usa cache).
    """
    now = datetime.now(timezone.utc)
    
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


class AvailablePeriod(BaseModel):
    """Periodo disponible para consultar"""
    month: int
    year: int
    label: str
    is_current: bool
    is_saved: bool
    total_kwh: float | None = None
    total_cost: float | None = None
    generated_at: datetime | None = None
    expires_at: datetime | None = None
    days_until_expiration: int | None = None

@router.get("/monthly/available-periods", response_model=dict)
def get_available_report_periods(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Lista periodos disponibles para generar reportes.
    
    Retorna:
    - Mes actual (siempre disponible, tiempo real)
    - Meses anteriores guardados (con info completa)
    
    Usa este endpoint para:
    - Mostrar selector de meses en tu app
    - Ver cuáles reportes están guardados
    - Saber cuándo expiran los reportes guardados
    """
    from app.repositories import ReportRepository
    
    now = datetime.now(timezone.utc)
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    periods = []
    
    # 1. Mes actual (siempre disponible)
    periods.append({
        "month": now.month,
        "year": now.year,
        "label": f"{month_names[now.month]} {now.year}",
        "is_current": True,
        "is_saved": False,
        "total_kwh": None,
        "total_cost": None,
        "generated_at": None,
        "expires_at": None,
        "days_until_expiration": None
    })
    
    # 2. Meses guardados en BD
    report_repo = ReportRepository(db)
    saved_reports = report_repo.get_all_by_user(current_user.user_id)
    
    for report in saved_reports:
        # No duplicar el mes actual
        if report.mr_month == now.month and report.mr_year == now.year:
            continue
        
        days_left = (report.mr_expires_at - now).days if report.mr_expires_at else None
        
        periods.append({
            "month": report.mr_month,
            "year": report.mr_year,
            "label": f"{month_names[report.mr_month]} {report.mr_year}",
            "is_current": False,
            "is_saved": True,
            "total_kwh": float(report.mr_total_kwh) if report.mr_total_kwh else None,
            "total_cost": float(report.mr_total_cost) if report.mr_total_cost else None,
            "generated_at": report.mr_generated_at,
            "expires_at": report.mr_expires_at,
            "days_until_expiration": days_left
        })
    
    # Ordenar por año y mes descendente
    periods.sort(key=lambda x: (x['year'], x['month']), reverse=True)
    
    return {
        "available_periods": periods,
        "total_periods": len(periods)
    }


