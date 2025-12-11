# 🌱 EcoWatt - Backend API

**Versión:** 1.0.1  
**Última actualización:** Diciembre 2025

Sistema backend completo para monitoreo inteligente de consumo eléctrico en tiempo real, con análisis predictivo mediante IA, control remoto de dispositivos IoT y generación automática de reportes mensuales.

---

## 📋 Tabla de Contenidos
- [Explicacion del backend](#-explicacion-del-backend)
- [Características Principales](#-características-principales)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Stack Tecnológico](#-stack-tecnológico)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación y Configuración](#-instalación-y-configuración)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [API Endpoints](#-api-endpoints)
- [Servicios en Tiempo Real](#-servicios-en-tiempo-real)
- [Sistema de Análisis IA](#-sistema-de-análisis-ia)
- [Infraestructura y Deployment](#-infraestructura-y-deployment)
- [Desarrollo y Testing](#-desarrollo-y-testing)
- [Troubleshooting](#-troubleshooting)
- [Contribución](#-contribución)
- [Licencia](#-licencia)

---

## 🚀 Explicacion del Backend

# Arquitectura Funcional por Módulos

Esta sección describe, a nivel conceptual, cómo trabaja cada módulo del backend y qué servicio aporta al sistema.

---

### 1. Módulo de Usuarios (`users`)
Gestiona todo lo relacionado con el ciclo de vida de un usuario dentro del sistema.  
Incluye registro, actualización de perfil, consulta del usuario autenticado y administración de atributos individuales como tarifa eléctrica o día de corte.  
Este módulo coordina validaciones, reglas de negocio y persistencia para garantizar que la información del usuario sea consistente y segura.

---

### 2. Módulo de Autenticación (`auth`)
Implementa el sistema de autenticación basado en JWT.  
Emite tokens de acceso y tokens de refresco, valida credenciales, gestiona la renovación de sesiones y controla la revocación de tokens.  
Permite que los usuarios accedan a rutas protegidas sin reenviar credenciales en cada solicitud, manteniendo seguridad y escalabilidad.

---

### 3. Módulo de Dispositivos (`devices`)
Administra los dispositivos asociados a cada usuario.  
Permite registrar nuevos dispositivos mediante su hardware ID, consultar la lista de dispositivos vinculados, obtener detalles individuales, renombrarlos o eliminarlos.  
Sirve como base para que los dispositivos físicos puedan enviar datos al sistema, como consumo energético u otros valores relevantes.

---

### 4. Módulo de Tarifas Eléctricas (`tariffs`)
Maneja las tarifas de energía que utiliza el backend para cálculos relacionados con consumo o análisis.  
Soporta tarifas definidas por rangos de fechas para permitir actualizaciones sin afectar periodos previos.  
Es un módulo clave para cualquier futura función de estimación, cálculo de costos o recomendaciones.

---

### 5. Módulo de Tokens y Sesiones (`refresh_tokens`)
Controla el almacenamiento y validación de tokens de refresco emitidos a cada usuario.  
Permite revocar sesiones de forma granular, incrementar la seguridad y garantizar que solo sesiones válidas continúen activas.  
Complementa el sistema de autenticación principal.

---

### 6. Módulo de Base de Datos (`database`)
Provee la conexión centralizada a PostgreSQL mediante SQLAlchemy.  
Gestiona la creación de sesiones, el manejo transaccional y la comunicación con los repositorios.  
Es el puente entre la API y la capa de persistencia.

---

### 7. Módulo de Modelos (`models`)
Define las tablas y entidades que existen en la base de datos.  
Cada modelo representa un recurso del sistema, como usuarios, dispositivos, tarifas o tokens de refresco.  
Estandariza la estructura de datos y garantiza integridad a través de relaciones y restricciones.

---

### 8. Módulo de Repositorios (`repositories`)
Capa encargada de leer, escribir y actualizar información en la base de datos.  
Agrupa toda la lógica de persistencia y abstrae las consultas, proporcionando métodos reutilizables y seguros para los servicios.  
Gracias a esta separación, los servicios se enfocan únicamente en reglas de negocio y no en detalles de SQL.

---

### 9. Módulo de Servicios (`services`)
Contiene la lógica de negocio principal del backend.  
Cada servicio usa los repositorios para obtener datos, aplica reglas y validaciones, transforma información y responde de forma coherente a los routers.  
Es la capa que orquesta el funcionamiento interno del sistema.

---

### 10. Módulo de Routers (`routers`)
Expone los endpoints públicos de la API.  
Recibe las solicitudes HTTP, valida los datos de entrada mediante esquemas y delega el procesamiento a los servicios.  
Define rutas como `/auth`, `/users`, `/devices` o `/tariffs`, manteniendo la API ordenada y modular.

---

### 11. Módulo de Configuración (`core`)
Centraliza variables de entorno, llaves secretas, configuraciones globales y utilidades comunes.  
Permite que la aplicación se adapte fácilmente a entornos locales o de producción sin modificar código.  
También ayuda a mantener parámetros sensibles fuera del repositorio.

---

### 12. Punto de Entrada (`main.py`)
Inicializa la aplicación FastAPI, carga todos los routers, configura CORS, registra middlewares y establece la estructura final del servidor.  
Es el archivo que se ejecuta tanto en desarrollo como en producción y que pone en marcha todos los módulos anteriores.

---

## 🚀 Características Principales

### Core Features
- ✅ **Monitoreo en Tiempo Real** - WebSocket para transmisión continua de datos de consumo
- ✅ **Control Remoto IoT** - Comandos MQTT para encender/apagar dispositivos Shelly
- ✅ **Análisis Predictivo con IA** - Detección automática de patrones anómalos (consumo vampiro, picos)
- ✅ **Reportes Mensuales Automáticos** - Generación y almacenamiento con expiración de 1 año
- ✅ **Notificaciones Push** - Firebase Cloud Messaging para alertas críticas
- ✅ **Autenticación JWT** - Tokens de acceso y refresco con rotación automática
- ✅ **Tarifas CFE Dinámicas** - Cálculo preciso de costos según tarifa (1, 1A-1F, DAC)
- ✅ **Huella de Carbono** - Estimación de impacto ambiental del consumo

### Integraciones
- 🔌 **Shelly IoT** - Compatible con Shelly 1PM Gen4 y Plus 1PM/2PM
- 📧 **Brevo API** - Envío de correos para recuperación de contraseña
- 🤖 **Google Gemini** - Generación de recomendaciones personalizadas
- 🔔 **Firebase** - Push notifications multi-dispositivo

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     CAPA DE PRESENTACIÓN                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Mobile App   │  │ WebSocket    │  │ REST API     │     │
│  │ (Flutter)    │  │ Clients      │  │ Consumers    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASTAPI APPLICATION                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Routers  │ WebSocket Manager │ MQTT Client      │  │
│  │ (v1/...)     │ (device streams)  │ (IoT control)    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Business Logic (Services)                            │  │
│  │ • Auth  • Devices  • Dashboard  • Reports  • AI     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Data Access Layer (Repositories)                     │  │
│  │ • PostgreSQL ORM  • Redis TimeSeries  • Cache       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAPA DE DATOS                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ PostgreSQL   │  │ Redis        │  │ MQTT Broker  │     │
│  │ (Relacional) │  │ (TimeSeries) │  │ (Mosquitto)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  SERVICIOS EXTERNOS                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Brevo API    │  │ Firebase FCM │  │ Gemini AI    │     │
│  │ (Email)      │  │ (Push)       │  │ (Análisis)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  TAREAS PROGRAMADAS (Celery)                │
│  • Análisis de patrones (cada hora)                         │
│  • Generación de reportes (mensual)                         │
│  • Limpieza de datos expirados (semanal)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Stack Tecnológico

### Backend Core
- **Framework:** FastAPI 0.115.0
- **ASGI Server:** Uvicorn + Gunicorn
- **Python:** 3.10+

### Bases de Datos
- **PostgreSQL** - Datos relacionales (usuarios, dispositivos, tarifas)
- **Redis Stack** - TimeSeries (métricas), Cache, Celery broker

### IoT & Comunicación
- **MQTT:** Paho-MQTT (control de dispositivos Shelly)
- **WebSocket:** Nativo FastAPI (streaming de datos en vivo)

### Autenticación & Seguridad
- **JWT:** python-jose + passlib + bcrypt
- **OAuth2:** FastAPI Security

### Servicios Externos
- **Brevo API:** Envío de correos transaccionales
- **Firebase Admin SDK:** Push notifications
- **Google Gemini:** IA generativa para recomendaciones

### Tareas Asíncronas
- **Celery:** Análisis periódicos y reportes
- **Celery Beat:** Scheduler de tareas programadas

### ORM & Validación
- **SQLAlchemy 2.0** - ORM moderno con type hints
- **Pydantic 2.9** - Validación de datos y schemas

---

## 📦 Requisitos Previos

### Software Necesario
```bash
# Sistema Operativo
Ubuntu 20.04+ / Debian 11+ (recomendado para producción)
macOS / Windows con WSL2 (desarrollo local)

# Runtime
Python 3.10 o superior
pip 21.0+

# Bases de Datos
PostgreSQL 14+
Redis Stack Server (con módulo TimeSeries)

# Opcional (Producción)
Docker & Docker Compose
Nginx (reverse proxy)
```

### Cuentas de Servicios (APIs)
- **Brevo** - API Key para envío de correos
- **Firebase** - Proyecto configurado con FCM
- **Google Cloud** - API Key para Gemini 2.0
- **MQTT Broker** - Mosquitto o HiveMQ

---

## 🚀 Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/ecowatt-backend.git
cd ecowatt-backend
```

### 2. Crear Entorno Virtual
```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Crear archivo `.env` en la raíz del proyecto:

```env
# === BASE DE DATOS ===
URL_DATABASE_SQL=postgresql://ecowatt_user:password@localhost:5432/ecowatt
URL_DATABASE_REDIS=redis://localhost:6379/0

# === SEGURIDAD JWT ===
KEY_SECRET=tu-clave-secreta-super-segura-cambiar-en-produccion
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# === BREVO API (Correo) ===
BREVO_API_KEY=xkeysib-tu-api-key-de-brevo
BREVO_SENDER_EMAIL=noreply@tudominio.com

# === FIREBASE (Push Notifications) ===
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# === GEMINI AI ===
GEMINIS_API_KEY=AIzaSy...tu-api-key-de-google

# === MQTT (Control IoT) ===
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_SHELLY_HOST=localhost
MQTT_SHELLY_PORT=1883
MQTT_SHELLY_USER=ecowatt_shelly
MQTT_SHELLY_PASS=tu-password-mqtt

# === OTROS ===
CARBON_EMISSION_FACTOR_KG_PER_KWH=0.527
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... (opcional)
```

### 5. Configurar PostgreSQL
```bash
# Crear usuario y base de datos
sudo -u postgres psql

CREATE USER ecowatt_user WITH PASSWORD 'tu_password';
CREATE DATABASE ecowatt OWNER ecowatt_user;
GRANT ALL PRIVILEGES ON DATABASE ecowatt TO ecowatt_user;
\q
```

Ejecutar migraciones:
```bash
# Crear tablas
psql -U ecowatt_user -d ecowatt -f archives_database/create_table.sql

# Poblar tarifas CFE
psql -U ecowatt_user -d ecowatt -f archives_database/records.sql
```

### 6. Instalar y Configurar Redis Stack
```bash
# Usando Docker (recomendado)
docker run -d \
  --name ecowatt-redis \
  -p 6379:6379 \
  -p 8001:8001 \
  redis/redis-stack-server:latest

# O ejecutar script de instalación
chmod +x app/scripts/install_redis.sh
./app/scripts/install_redis.sh
```

### 7. Configurar Firebase
1. Descargar `firebase-credentials.json` desde Firebase Console
2. Colocarlo en la raíz del proyecto
3. Actualizar la ruta en `.env`

### 8. Iniciar el Servidor
```bash
# Desarrollo (con hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción (con Gunicorn)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### 9. Iniciar Workers de Celery
```bash
# En terminal separada (Worker)
celery -A app.main.celery_app worker --loglevel=info

# En otra terminal (Beat Scheduler)
celery -A app.main.celery_app beat --loglevel=info
```

---

## 📁 Estructura del Proyecto

```
ecowatt/
├── app/
│   ├── core/                      # Configuración central
│   │   ├── settings.py           # Variables de entorno
│   │   ├── security.py           # JWT y autenticación
│   │   ├── logger.py             # Sistema de logs
│   │   ├── mqtt_client.py        # Cliente MQTT global
│   │   ├── websocket_manager.py  # Gestor de conexiones WS
│   │   └── discord_logger.py     # Alertas a Discord
│   │
│   ├── database/                  # Gestión de BDs
│   │   └── database.py           # Conexiones SQL/Redis
│   │
│   ├── models/                    # Modelos SQLAlchemy
│   │   ├── user.py               # Tabla tbusers
│   │   ├── device.py             # Tabla tbdevice
│   │   ├── tarrif.py             # Tabla tbtarrifs
│   │   ├── report.py             # Tabla tbmonthlyreports
│   │   ├── alert.py              # Tabla tbalerts
│   │   ├── recommendation.py     # Tabla tbrecommendations
│   │   ├── refresh_token.py      # Tabla tbrefreshtokens
│   │   ├── password_reset_token.py
│   │   └── fcm_token.py          # Tabla tbfcmtokens
│   │
│   ├── repositories/              # Capa de acceso a datos
│   │   ├── user_repository.py
│   │   ├── device_repository.py
│   │   ├── tarrif_repository.py
│   │   ├── report_repository.py
│   │   ├── timeseries_repository.py  # Redis TimeSeries
│   │   └── ...
│   │
│   ├── schemas/                   # Modelos Pydantic (DTOs)
│   │   ├── user_schema.py
│   │   ├── device_schema.py
│   │   ├── dashboard_schema.py
│   │   ├── monthly_report_schema.py
│   │   └── ...
│   │
│   ├── services/                  # Lógica de negocio
│   │   ├── auth_service.py       # Login, refresh, logout
│   │   ├── device_service.py     # CRUD dispositivos
│   │   ├── device_control_service.py  # Control MQTT
│   │   ├── dashboard_service.py  # Resumen consumo
│   │   ├── report_service.py     # Generación reportes
│   │   ├── analysis_service.py   # Análisis IA
│   │   ├── ingest_service.py     # Procesar datos Shelly
│   │   ├── notification_service.py  # FCM push
│   │   └── ...
│   │
│   ├── routers/                   # Endpoints API
│   │   ├── auth_router.py        # /api/v1/auth
│   │   ├── user_router.py        # /api/v1/users
│   │   ├── device_router.py      # /api/v1/devices
│   │   ├── device_control_router.py  # /api/v1/control
│   │   ├── dashboard_router.py   # /api/v1/dashboard
│   │   ├── history_router.py     # /api/v1/history
│   │   ├── report_router.py      # /api/v1/reports
│   │   ├── ingest_router.py      # /api/v1/ingest
│   │   ├── websocket_router.py   # /ws/live/{device_id}
│   │   └── fcm_token_router.py   # /api/v1/fcm
│   │
│   └── main.py                    # Punto de entrada FastAPI
│
├── archives_database/             # Scripts SQL
│   ├── create_database.sql
│   ├── create_table.sql
│   └── records.sql               # Tarifas CFE 2025
│
├── logs/                          # Archivos de log
│   └── backend.log
│
├── .env                           # Variables de entorno
├── requirements.txt               # Dependencias Python
├── simulator_shelly.py            # Simulador IoT para testing
├── test_notification.py           # Script de prueba FCM
└── README.md                      # Este archivo
```

---

## 🔌 API Endpoints

### Base URL
```
https://core-cloud.dev/api/v1
```

### Autenticación (`/auth`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/auth/login` | Iniciar sesión | ❌ |
| POST | `/auth/refresh` | Renovar access token | ❌ |
| POST | `/auth/logout` | Cerrar sesión | ❌ |
| POST | `/auth/forgot-password` | Recuperar contraseña | ❌ |
| POST | `/auth/reset-password` | Cambiar contraseña | ❌ |

**Ejemplo Login:**
```bash
curl -X POST https://core-cloud.dev/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "usuario@ejemplo.com",
    "user_password": "password123"
  }'
```

**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a7f3d2c1b9e8f5d4c3b2a1...",
  "token_type": "Bearer"
}
```

---

### Usuarios (`/users`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/users/` | Registrar usuario | ❌ |
| GET | `/users/me` | Perfil del usuario | ✅ |
| PATCH | `/users/me` | Actualizar perfil | ✅ |

---

### Dispositivos (`/devices`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/devices/` | Registrar dispositivo | ✅ |
| GET | `/devices/` | Listar mis dispositivos | ✅ |
| GET | `/devices/{dev_id}` | Ver dispositivo | ✅ |
| PATCH | `/devices/{dev_id}` | Actualizar nombre | ✅ |
| PATCH | `/devices/{dev_id}/status` | Activar/Desactivar | ✅ |
| DELETE | `/devices/{dev_id}` | Eliminar dispositivo | ✅ |

---

### Control de Dispositivos (`/control`) 🆕

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/control/{dev_id}/toggle` | Alternar ON/OFF | ✅ |
| POST | `/control/{dev_id}/set` | Forzar estado | ✅ |
| POST | `/control/{dev_id}/on` | Encender | ✅ |
| POST | `/control/{dev_id}/off` | Apagar | ✅ |
| GET | `/control/{dev_id}/status` | Estado actual | ✅ |

**Ejemplo Encender Dispositivo:**
```bash
curl -X POST https://core-cloud.dev/api/v1/control/5/on \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Respuesta:**
```json
{
  "success": true,
  "message": "Comando ejecutado correctamente",
  "device_name": "Cocina Principal",
  "was_on": false,
  "new_state": true,
  "action": "encendido"
}
```

---

### Dashboard (`/dashboard`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/dashboard/summary` | Resumen de consumo actual | ✅ |

**Respuesta:**
```json
{
  "kwh_consumed_cycle": 125.45,
  "estimated_cost_mxn": 342.78,
  "billing_cycle_start": "2025-12-01",
  "billing_cycle_end": "2025-12-31",
  "days_in_cycle": 9,
  "current_tariff": "1f",
  "carbon_footprint": {
    "co2_emitted_kg": 66.11,
    "equivalent_trees_absorption_per_year": 3.0050
  },
  "latest_recommendation": "Revisa si algún cargador quedó conectado..."
}
```

---

### Historial (`/history`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/history/graph?period=daily` | Gráfica de consumo | ✅ |
| GET | `/history/last7days` | Últimos 7 días | ✅ |

**Periodos válidos:** `daily`, `weekly`, `monthly`

---

### Reportes Mensuales (`/reports`) 🆕

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/reports/monthly/current` | Reporte mes actual | ✅ |
| POST | `/reports/monthly` | Generar reporte específico | ✅ |
| GET | `/reports/monthly/available-periods` | Periodos disponibles | ✅ |

**Ejemplo Generar Reporte:**
```bash
curl -X POST https://core-cloud.dev/api/v1/reports/monthly \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"month": 11, "year": 2025}'
```

---

### Ingesta de Datos (`/ingest`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/ingest/shelly` | Recibir datos de Shelly | ❌ |

**Payload esperado:**
```json
{
  "switch:0": {
    "id": 0,
    "apower": 1234.5,
    "voltage": 220.3,
    "current": 5.6
  },
  "sys": {
    "mac": "A8032412C3D4"
  }
}
```

---

### Tokens FCM (`/fcm`)

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/fcm/register` | Registrar token de dispositivo | ✅ |

---

## 🔴 Servicios en Tiempo Real

### WebSocket - Consumo en Vivo

**Conexión:**
```javascript
const ws = new WebSocket(
  'wss://core-cloud.dev/ws/live/5?token=YOUR_ACCESS_TOKEN'
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Watts:', data.watts);
  console.log('Volts:', data.volts);
  console.log('Amps:', data.amps);
};
```

**Flujo de Datos:**
```
Shelly Device → API (/ingest/shelly) → WebSocket Manager → Mobile App
     ↓
  Redis TimeSeries (almacenamiento histórico)
```

**Frecuencia:** ~1 mensaje cada 5 segundos (configurable en el dispositivo)

---

### MQTT - Control de Dispositivos

**Arquitectura:**
```
Mobile App → API (/control/...) → MQTT Client → Mosquitto → Shelly Device
                                        ↓
                                   Respuesta RPC
```

**Métodos RPC Soportados:**
- `Switch.Set` - Forzar estado ON/OFF
- `Switch.Toggle` - Alternar estado
- `Switch.GetStatus` - Consultar estado

**Configuración Topics:**
```
Comando:  {mqtt_prefix}-{device_mac}/rpc
Respuesta: ecowatt/backend/rpc_response
```

**Ejemplo Manual (mosquitto_pub):**
```bash
mosquitto_pub -h localhost -p 1883 \
  -t "shellyplus1pm-a8032412c3d4/rpc" \
  -m '{
    "id": 1,
    "src": "ecowatt/backend/rpc_response",
    "method": "Switch.Toggle",
    "params": {"id": 0}
  }'
```

---

## 🤖 Sistema de Análisis IA

### Tareas Programadas (Celery Beat)

| Tarea | Frecuencia | Descripción |
|-------|-----------|-------------|
| `run_analysis` | Cada hora | Análisis de patrones de consumo |
| `generate_previous_month_reports` | Día 1, 2:00 AM | Reportes automáticos |
| `cleanup_expired_reports_job` | Domingos, 3:00 AM | Limpieza de reportes >1 año |

### Detecciones Automáticas

#### 1. Consumo Vampiro
```python
# Configuración
VAMPIRE_CONSUMPTION_THRESHOLD_WATTS = 20
VAMPIRE_ANALYSIS_START_HOUR_UTC = 7  # 1 AM CST
VAMPIRE_ANALYSIS_END_HOUR_UTC = 11   # 5 AM CST
```

**Proceso:**
1. Analiza datos de 01:00 - 05:00 (hora local)
2. Calcula promedio de consumo nocturno
3. Si promedio > 20W: genera alerta + recomendación IA

#### 2. Picos de Consumo
```python
HIGH_PEAK_THRESHOLD_WATTS = 1500
HIGH_PEAK_MIN_DURATION_MINUTES = 5
```

**Proceso:**
1. Analiza últimas 3 horas
2. Detecta sostenimiento >1500W por >5 minutos
3. Genera alerta + análisis de posibles causas

### Recomendaciones con Gemini AI

**Prompt Engineering:**
```python
# Ejemplo: Consumo Vampiro
prompt = f"""
Detectamos consumo vampiro de {value} en el circuito '{device_name}' 
durante la noche. Da 3 consejos CONCRETOS y BREVES (máximo 2 líneas 
cada uno) para identificar qué aparato está causándolo. Formato: Usa 
números (1., 2., 3.) y sé MUY específico con ejemplos de aparatos 
comunes en ese circuito. Máximo 60 palabras en total.
"""
```

**Modelo:** `gemini-2.0-flash-exp`

---

## 🏭 Infraestructura y Deployment

### Servidor VPS (DigitalOcean)

**Specs Recomendadas:**
- **CPU:** 2 vCPUs
- **RAM:** 4 GB
- **Storage:** 80 GB SSD
- **OS:** Ubuntu 22.04 LTS

### Configuración de Producción

#### 1. Systemd Service (FastAPI)
```ini
# /etc/systemd/system/ecowatt-api.service
[Unit]
Description=EcoWatt FastAPI Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=ecowatt
WorkingDirectory=/home/ecowatt/ecowatt-backend
Environment="PATH=/home/ecowatt/ecowatt-backend/venv/bin"
ExecStart=/home/ecowatt/ecowatt-backend/venv/bin/gunicorn \
    app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/ecowatt/access.log \
    --error-logfile /var/log/ecowatt/error.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Systemd Service (Celery Worker)
```ini
# /etc/systemd/system/ecowatt-worker.service
[Unit]
Description=EcoWatt Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=ecowatt
WorkingDirectory=/home/ecowatt/ecowatt-backend
Environment="PATH=/home/ecowatt/ecowatt-backend/venv/bin"
ExecStart=/home/ecowatt/ecowatt-backend/venv/bin/celery \
    -A app.main.celery_app worker \
    --loglevel=info \
    --logfile=/var/log/ecowatt/celery-worker.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. Systemd Service (Celery Beat)
```ini
# /etc/systemd/system/ecowatt-beat.service
[Unit]
Description=EcoWatt Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=ecowatt
WorkingDirectory=/home/ecowatt/ecowatt-backend
Environment="PATH=/home/ecowatt/ecowatt-backend/venv/bin"
ExecStart=/home/ecowatt/ecowatt-backend/venv/bin/celery \
    -A app.main.celery_app beat \
    --loglevel=info \
    --logfile=/var/log/ecowatt/celery-beat.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
