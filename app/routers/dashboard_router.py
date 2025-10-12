# app/routers/dashboard_router.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from redis import Redis

from app.database import get_db, get_redis_client
from app.core import TokenData, get_current_user
from app.schemas import DashboardSummary
from app.services import get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary_route(
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Obtiene un resumen completo del estado del consumo y costos
    para el ciclo de facturación actual del usuario autenticado.
    """
    summary_data = get_dashboard_summary(db, redis_client, current_user.user_id)
    if not summary_data or "error" in summary_data:
        detail = summary_data.get("error", "No se pudo generar el resumen.") if summary_data else "Error interno."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return DashboardSummary(**summary_data)