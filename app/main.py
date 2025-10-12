# app/main.py (VERSIÓN FINAL CORREGIDA)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# 1. Importar AMBOS routers desde el paquete de routers
from app.routers import api_router, websocket_router

api_description = """
API para el monitoreo de consumo eléctrico EcoWatt.

Esta API proporciona endpoints RESTful para la gestión de usuarios y dispositivos,
así como un endpoint de WebSocket para la transmisión de datos en tiempo real.

## WebSocket en Tiempo Real

Para recibir las mediciones de consumo en vivo, conéctese al siguiente endpoint:

* **URL:** `/ws/live/{device_id}`
* **Parámetros de Conexión:**
    * `device_id` (en la ruta): El ID del dispositivo que desea monitorear.
    * `token` (query param): El token de acceso (JWT) del usuario.
* **Ejemplo de URL de conexión:** `wss://core-cloud.dev/ws/live/1?token=eyJhbGciOi...`
* **Mensajes del Servidor:** El servidor enviará mensajes JSON con el siguiente formato:
    ```json
    {
      "watts": 1250.5,
      "volts": 127.2,
      "amps": 9.83
    }
    ```
"""


# 2. Tu configuración de FastAPI con Scalar está perfecta
app = FastAPI(
    title="EcoWatt API",
    description=api_description,
    version="1.0.1",
    docs_url=None,  # Deshabilita Swagger en /docs
    redoc_url=None  # Deshabilita ReDoc en /redoc
)


# 3. Tu middleware de CORS está bien
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Incluir el router principal de la API REST (con el prefijo /api/v1)
app.include_router(api_router)

# 5. NUEVO: Incluir el router de WebSocket por separado (sin prefijo adicional)
app.include_router(websocket_router.router)


# 6. Tu endpoint para la documentación de Scalar está perfecto
@app.get("/docs", response_class=HTMLResponse, tags=["Documentation"])
async def get_scalar_docs():
    return """
    <!doctype html>
    <html>
      <head>
        <title>EcoWatt API - Scalar</title>
        <meta charset="utf-8" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1" />
        <style>
          body {
            margin: 0;
          }
        </style>
      </head>
      <body>
        <script
          id="api-reference"
          data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bienvenido a la API de EcoWatt v1"}