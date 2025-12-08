# app/routers/ingest_router.py

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from redis import Redis

from app.database import get_db, get_redis_client
from app.schemas import ShellyIngestData
from app.services import process_shelly_data
from app.core import logger

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

@router.post("/shelly")
async def ingest_shelly_data(
    data: ShellyIngestData,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client)
):
    """
    Endpoint público para recibir datos de dispositivos Shelly.

    Procesa los datos en segundo plano para responder al Shelly instantáneamente
    y evitar que la petición se demore.
    """
    try:
        # Añadimos la tarea pesada (acceso a BDs) a un proceso en segundo plano.
        background_tasks.add_task(process_shelly_data, db, redis_client, data)

        # Respondemos inmediatamente al Shelly para que no tenga que esperar.
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Error en el endpoint de ingesta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al procesar los datos.")