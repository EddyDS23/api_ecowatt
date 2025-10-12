

from fastapi import APIRouter

# 1. Importar los routers individuales que has creado
from . import auth_router, user_router, device_router, ingest_router, dashboard_router

# 2. Crear un router principal que agrupará a todos los demás
api_router = APIRouter(prefix="/api/v1")

# 3. Incluir cada router individual en el router principal
api_router.include_router(auth_router.router)
api_router.include_router(user_router.router)
api_router.include_router(device_router.router)
api_router.include_router(ingest_router.router)
api_router.include_router(dashboard_router.router)
# Cuando crees más routers (alerts, recommendations, etc.), los añadirás aquí.
# api_router.include_router(alert_router.router)