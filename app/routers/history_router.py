
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from redis import Redis

from app.database import get_db, get_redis_client
from app.core import TokenData, get_current_user
from app.schemas import HistoryPeriod, HistoryResponse
from app.services import get_history_data

router = APIRouter(prefix="/history", tags=["History"])

@router.get("/graph", response_model=HistoryResponse)
def get_history_graph_route(period:HistoryPeriod = Query(...,description="El periodo de la grafica: 'daily', 'weekly', 'monthly'"),
                            db:Session = Depends(get_db),redis_client = Depends(get_redis_client),current_user:TokenData = Depends(get_current_user)):
    history_data = get_history_data(db, redis_client, current_user.user_id,period)

    if history_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron datos de consumo para el periodo solicitado o el usuario no tiene dispositivos activados "
        )
    
    return history_data
