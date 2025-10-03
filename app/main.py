# app/main.py (VERSIÓN ACTUALIZADA CON SCALAR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# 1. Importar el router principal desde el paquete de routers
from app.routers import api_router

# 2. Modificación: Deshabilitar las documentaciones por defecto
app = FastAPI(
    title="EcoWatt API",
    description="API para el monitoreo de consumo eléctrico.",
    version="1.0.0",
    docs_url=None,  # Deshabilita Swagger en /docs
    redoc_url=None  # Deshabilita ReDoc en /redoc
)


# Opcional pero recomendado: Añadir middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Incluir el router principal que contiene todos los demás
app.include_router(api_router)

# 4. NUEVO: Añadir el endpoint para la documentación de Scalar
@app.get("/docs", response_class=HTMLResponse, tags=["Documentation"])
async def get_scalar_docs():
    # El HTML y JavaScript para renderizar Scalar
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