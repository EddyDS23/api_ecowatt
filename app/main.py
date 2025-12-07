from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.schedules import crontab
from app.core import settings, logger
from app.services import analyze_consumption_patterns
from app.core.discord_logger import send_discord_alert
from app.routers import api_router, websocket_router, device_control_router
import firebase_admin
from firebase_admin import credentials
from contextlib import asynccontextmanager
from app.core.mqtt_client import mqtt_client

import os
from datetime import datetime, timezone

os.environ['TZ'] = 'UTC'

import time
time.tzset()


if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK inicializado correctamente.")
    except Exception as e:
        logger.error(f"Error al inicializar Firebase Admin SDK: {e}")
else:
    logger.info("Firebase Admin SDK ya estaba inicializado (worker reutilizado).")



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

    # Generar reportes automáticamente (día 1 de cada mes, 2 AM)
    sender.add_periodic_task(
        crontab(minute='0', hour='2', day_of_month='1'),
        generate_previous_month_reports.s(),
        name='Generar reportes del mes anterior'
    )
    
    # Limpiar reportes expirados (domingos, 3 AM)
    sender.add_periodic_task(
        crontab(minute='0', hour='3', day_of_week='0'),
        cleanup_expired_reports_job.s(),
        name='Limpiar reportes expirados'
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

@celery_app.task
def generate_previous_month_reports():
    """
    🔥 TAREA PRINCIPAL: Se ejecuta el día 1 de cada mes.
    Genera reportes del mes anterior para todos los usuarios.
    """
    from app.database import SessionLocal, redis_client
    from app.repositories import DeviceRepository, ReportRepository
    from app.services.report_service import _generate_report_from_redis
    from dateutil.relativedelta import relativedelta
    
    logger.info("=" * 70)
    logger.info("🚀 GENERACIÓN AUTOMÁTICA DE REPORTES MENSUALES")
    logger.info("=" * 70)
    
    db = SessionLocal()
    
    try:
        # Calcular mes anterior
        now = datetime.now(timezone.utc)
        prev_month = now - relativedelta(months=1)
        target_month = prev_month.month
        target_year = prev_month.year
        
        logger.info(f"📅 Mes objetivo: {target_month}/{target_year}")
        
        # Obtener usuarios con dispositivos activos
        device_repo = DeviceRepository(db)
        devices = device_repo.get_all_active_devices()
        user_ids = list(set(d.dev_user_id for d in devices))
        
        logger.info(f"👥 Usuarios a procesar: {len(user_ids)}")
        
        report_repo = ReportRepository(db)
        stats = {"success": 0, "skipped": 0, "errors": 0}
        
        for user_id in user_ids:
            try:
                # Verificar si ya existe
                existing = report_repo.get_by_month(user_id, target_month, target_year)
                if existing:
                    logger.info(f"⏭️  Usuario {user_id}: Ya existe")
                    stats["skipped"] += 1
                    continue
                
                # Generar reporte
                logger.info(f"📊 Generando para usuario {user_id}...")
                report = _generate_report_from_redis(db, redis_client, user_id, target_month, target_year)
                
                if report:
                    # Guardar
                    saved = report_repo.save(
                        user_id=user_id,
                        month=target_month,
                        year=target_year,
                        report_data=report.model_dump(mode='json'),
                        total_kwh=float(report.executive_summary.total_kwh_consumed),
                        total_cost=float(report.executive_summary.total_estimated_cost_mxn)
                    )
                    
                    if saved:
                        logger.info(f"✅ Usuario {user_id}: Guardado")
                        stats["success"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    logger.warning(f"⚠️  Usuario {user_id}: Sin datos")
                    stats["errors"] += 1
                    
            except Exception as e:
                logger.error(f"❌ Error usuario {user_id}: {e}")
                stats["errors"] += 1
        
        logger.info("=" * 70)
        logger.info(f"📊 RESUMEN:")
        logger.info(f"   ✅ Exitosos: {stats['success']}")
        logger.info(f"   ⏭️  Omitidos: {stats['skipped']}")
        logger.info(f"   ❌ Errores: {stats['errors']}")
        logger.info(f"   📋 Total: {len(user_ids)}")
        logger.info("=" * 70)
        
        return stats
        
    except Exception as e:
        logger.exception(f"❌ Error crítico: {e}")
        return {"error": str(e)}
    finally:
        db.close()

@celery_app.task
def cleanup_expired_reports_job():
    """Elimina reportes con más de 1 año"""
    from app.repositories import ReportRepository
    from app.database import SessionLocal
    
    db = SessionLocal()
    try:
        repo = ReportRepository(db)
        deleted = repo.delete_expired()
        logger.info(f"🧹 Limpieza: {deleted} reportes eliminados")
        return deleted
    finally:
        db.close()


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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- CÓDIGO DE ARRANQUE (Startup) ---
    logger.info("🚀 Iniciando API EcoWatt...")
    mqtt_client.connect()
    
    yield  # <-- Aquí es donde la API se queda corriendo y escuchando peticiones
    
    # --- CÓDIGO DE CIERRE (Shutdown) ---
    logger.info("🛑 Deteniendo servicios...")
    mqtt_client.disconnect()


app = FastAPI(
    title="EcoWatt API",
    description=api_description,
    version="1.0.1",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
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
app.include_router(device_control_router)

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
