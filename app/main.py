# app/main.py (VERSIÓN FINAL Y LIMPIA)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Importar el router principal desde el paquete de routers
from app.routers import api_router

app = FastAPI(
    title="EcoWatt API",
    description="API para el monitoreo de consumo eléctrico.",
    version="1.0.0"
)


# Opcional pero recomendado: Añadir middleware de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, deberías ser más restrictivo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Incluir el router principal que contiene todos los demás
app.include_router(api_router)

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Bienvenido a la API de EcoWatt v1"}