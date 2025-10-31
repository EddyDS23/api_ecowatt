from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.schedules import crontab
from app.core import settings, logger
from app.services import analyze_consumption_patterns
from app.core.discord_logger import send_discord_alert
from app.routers import api_router, websocket_router
import firebase_admin
from firebase_admin import credentials

import os
from datetime import timezone

os.environ['TZ'] = 'UTC'

import time
time.tzset()

try:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK inicializado correctamente.")
except Exception as e:
    logger.error(f"Error al inicializar Firebase Admin SDK: {e}")




# --- Configuración de Celery ---
celery_app = Celery(
    'tasks',
    broker=settings.URL_DATABASE_REDIS,
    backend=settings.URL_DATABASE_REDIS
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    broker_connection_retry_on_startup=True
)


# --- Definición de Tareas Programadas (Celery Beat) ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configura las tareas que se ejecutarán periódicamente.
    """
    logger.info("Configurando tareas periódicas de Celery...")
    sender.add_periodic_task(
        crontab(minute='0', hour='11'),  # Cada hora
        run_analysis.s(),
        name='Analizar consumo de energía cada hora'
    )


# --- Tarea de Celery ---
@celery_app.task
def run_analysis():
    """
    Tarea de Celery: ejecuta el análisis de consumo.
    """
    logger.info("--- [CELERY TASK]: Iniciando análisis de patrones de consumo ---")
    try:
        analyze_consumption_patterns()
        logger.info("--- [CELERY TASK]: Análisis de patrones completado exitosamente ---")
        send_discord_alert("Análisis de consumo completado exitosamente.", level="INFO")
    except Exception as e:
        logger.error(f"--- [CELERY TASK]: Ocurrió un error durante el análisis: {e} ---")
        send_discord_alert(f"Error en análisis de consumo: {e}", level="ERROR")


# --- Configuración de FastAPI ---
api_description = """
API para el monitoreo de consumo eléctrico EcoWatt.

Esta API proporciona endpoints RESTful para la gestión de usuarios y dispositivos,
así como un endpoint de WebSocket para la transmisión de datos en tiempo real.

## WebSocket en Tiempo Real

* **URL:** `/ws/live/{device_id}`
* **Parámetros de Conexión:**
    * `device_id` — ID del dispositivo.
    * `token` — Token JWT del usuario.
* **Ejemplo:** `wss://core-cloud.dev/ws/live/1?token=eyJhbGciOi...`
"""

app = FastAPI(
    title="EcoWatt API",
    description=api_description,
    version="1.0.1",
    docs_url=None,
    redoc_url=None
)


# --- Middleware CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Routers ---
app.include_router(api_router)
app.include_router(websocket_router.router)


# --- Documentación Scalar ---
@app.get("/docs", response_class=HTMLResponse, tags=["Documentation"])
async def get_scalar_docs():
    return """
    <!doctype html>
    <html>
      <head>
        <title>EcoWatt API - Scalar</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>body { margin: 0; }</style>
      </head>
      <body>
        <script id="api-reference" data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """


@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bienvenido a la API de EcoWatt v1"}


# --- Manejo global de errores ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    message = f"Error 500 en {request.url.path}: {exc}"
    send_discord_alert(message, level="CRITICAL")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor."}
    )


# --- Notificación al iniciar la API ---
send_discord_alert("API EcoWatt iniciada correctamente.", level="INFO")
