# Documentación Técnica y de Infraestructura - Proyecto EcoWatt
_Versión: 1.0 | Fecha: 03 de Octubre de 2025_

Este documento consolida la información técnica del backend de la aplicación EcoWatt y la configuración de la infraestructura del servidor que lo aloja.

---

## **Parte 1: Arquitectura del Backend (Software)**

### **1. Descripción General**

El backend de EcoWatt es una API RESTful diseñada para servir como el núcleo de la aplicación móvil de monitoreo de energía. Proporciona funcionalidades para la gestión de usuarios, dispositivos, y el procesamiento de datos de consumo para generar analíticas y recomendaciones de ahorro.

- **Framework Principal:** FastAPI (Python)
- **Base de Datos Relacional:** PostgreSQL
- **Base de Datos en Memoria (Roadmap):** Redis
- **Autenticación:** JWT (JSON Web Tokens) con Tokens de Acceso y de Refresco.
- **Hardware Soportado:** Shelly 1PM Gen4 (y otros dispositivos con API local).

---

### **2. Estructura del Proyecto (Directorios)**

El proyecto sigue una arquitectura en capas para promover la separación de responsabilidades y facilitar el mantenimiento.

```text
/ecowatt/
├── app/                     # Directorio principal del código fuente.
│   ├── core/                # Módulos de configuración central y utilidades.
│   ├── database/            # Gestión de la conexión a las bases de datos.
│   ├── models/              # Define las tablas de la base de datos (SQLAlchemy).
│   ├── repositories/        # Capa de acceso a datos (consultas a la BD).
│   ├── schemas/             # Define los modelos de datos de la API (Pydantic).
│   ├── services/            # Contiene la lógica de negocio principal.
│   ├── routers/             # Define los endpoints (rutas) de la API.
│   └── main.py              # Punto de entrada de la aplicación FastAPI.
│
├── database_archvices/      # Scripts SQL para la gestión de la base de datos.
│
├── venv/                    # Entorno virtual de Python.
│
├── .env                     # Archivo de configuración con variables de entorno.
└── requirements.txt         # Lista de dependencias de Python.
```

---

### **3. Modelo de Datos (PostgreSQL)**

La base de datos relacional almacena la información persistente del sistema.

- **`tbUsers`:** Almacena la información de los usuarios, su tarifa de CFE y el día de corte.
- **`tbDevice`:** Almacena los dispositivos de monitoreo (Shelly) asociados a cada usuario, identificados por su `dev_hardware_id`.
- **`tbTarrifs`:** Estructura flexible para almacenar las tarifas escalonadas de CFE, con rangos de fecha para manejar actualizaciones.
- **`tbRefreshTokens`:** Almacena los tokens de refresco que permiten mantener la sesión del usuario abierta en la app móvil.
- **`tbAlerts`:** *(Roadmap)* Guardará las notificaciones push generadas por el sistema.
- **`tbRecommendations`:** *(Roadmap)* Guardará las recomendaciones de ahorro generadas por la IA.

---

### **4. Endpoints Implementados (V1)**

Todos los endpoints están agrupados bajo el prefijo `/api/v1/`.

#### Autenticación (`/auth`)
- **`POST /login`:** Inicia sesión y devuelve Access/Refresh Tokens.
- **`POST /refresh`:** Solicita un nuevo Access Token.
- **`POST /logout`:** Invalida un Refresh Token para cerrar la sesión.

#### Usuarios (`/users`)
- **`POST /`:** Endpoint público para registrar un nuevo usuario.
- **`GET /me`:** (Protegido) Obtiene la información del perfil del usuario autenticado.
- **`PATCH /me`:** (Protegido) Actualiza la información del perfil.

#### Dispositivos (`/devices`)
- **`POST /`:** (Protegido) Registra un nuevo dispositivo Shelly.
- **`GET /`:** (Protegido) Obtiene la lista de dispositivos del usuario.
- **`GET /{dev_id}`:** (Protegido) Obtiene la información de un dispositivo específico.
- **`PATCH /{dev_id}`:** (Protegido) Actualiza el nombre de un dispositivo.
- **`DELETE /{dev_id}`:** (Protegido) Elimina un dispositivo.

---

### **5. Cómo Correr la API Localmente**

1.  Asegurarse de estar en la carpeta raíz del proyecto (`ecowatt/`).
2.  Activar el entorno virtual:
    ```bash
    source venv/bin/activate
    ```
3.  Ejecutar el servidor Uvicorn:
    ```bash
    uvicorn app.main:app --reload
    ```
4.  Acceder a la documentación interactiva en: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---
---

## **Parte 2: Resumen de Infraestructura (Servidor)**

Este apartado resume la configuración inicial del servidor que aloja la aplicación.

### **1. Provisión del Servidor**
- **Proveedor de Cloud:** DigitalOcean.
- **Tipo de Instancia:** Droplet (Servidor Privado Virtual - VPS).
- **Estado:** El servidor ha sido provisionado y se encuentra operativo, con recursos asignados para cubrir las necesidades del proyecto a mediano plazo (12 meses).

### **2. Configuración del Dominio (DNS)**
- **Objetivo:** Vincular un dominio registrado a la dirección IP pública del servidor.
- **Método:** Se delegó la gestión del DNS a los nameservers de DigitalOcean.
- **Estado:** La configuración se ha completado y la propagación del DNS ha sido verificada. El dominio resuelve correctamente a la IP del servidor.

### **3. Seguridad y Acceso Remoto (SSH)**
- **Objetivo:** Implementar un método de acceso remoto seguro al servidor.
- **Método:** Se ha establecido un plan para migrar del acceso por contraseña al acceso mediante **llaves SSH**, un estándar de la industria para la seguridad en servidores.
- **Plan de Contingencia:** Se ha documentado el procedimiento para utilizar la consola de recuperación de DigitalOcean en caso de pérdida de la llave SSH.