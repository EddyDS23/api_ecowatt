# app/routers/__init__.py 

from fastapi import APIRouter

# 1. Importar todos los routers
from . import auth_router, user_router, device_router, ingest_router, dashboard_router, history_router, websocket_router

# 2. Crear el router para la API REST con el prefijo v1
api_router = APIRouter(prefix="/api/v1")

# 3. Incluir solo los routers de la API REST
api_router.include_router(auth_router.router)
api_router.include_router(user_router.router)
api_router.include_router(device_router.router)
api_router.include_router(ingest_router.router)
api_router.include_router(dashboard_router.router)
api_router.include_router(history_router.router)

# El websocket_router no se incluye aquí para evitar el prefijo