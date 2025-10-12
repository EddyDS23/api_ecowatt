#!/bin/bash

# --- Script para Instalar Docker y Desplegar Redis Stack ---

# Colores para los mensajes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # Sin Color

echo -e "${YELLOW}--- Iniciando la configuración de Redis para EcoWatt ---${NC}"

# 1. Verificar si Docker está instalado
if ! command -v docker &> /dev/null
then
    echo "Docker no está instalado. Iniciando la instalación..."
    
    # Actualizar la lista de paquetes
    sudo apt-get update
    
    # Instalar paquetes necesarios para permitir a apt usar un repositorio sobre HTTPS
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Añadir la clave GPG oficial de Docker
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Configurar el repositorio de Docker
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Instalar Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Añadir el usuario actual al grupo de docker para no necesitar 'sudo'
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}Docker instalado exitosamente.${NC}"
    echo -e "${YELLOW}IMPORTANTE: Para usar Docker sin 'sudo', necesitas cerrar sesión y volver a entrar.${NC}"
else
    echo -e "${GREEN}Docker ya está instalado. Omitiendo instalación.${NC}"
fi

# 2. Verificar si el contenedor de Redis ya existe
if [ "$(docker ps -a -q -f name=ecowatt-redis)" ]; then
    echo "Un contenedor llamado 'ecowatt-redis' ya existe. Deteniéndolo y eliminándolo..."
    docker stop ecowatt-redis
    docker rm ecowatt-redis
fi

# 3. Iniciar el contenedor de Redis Stack Server
echo "Iniciando el contenedor de Redis Stack Server..."
docker run -d --name ecowatt-redis -p 6379:6379 -p 8001:8001 redis/redis-stack-server:latest

# 4. Verificar el estado del contenedor
sleep 5 # Darle unos segundos para que inicie
if [ "$(docker ps -q -f name=ecowatt-redis)" ]; then
    echo -e "${GREEN}--- ¡Éxito! Redis está corriendo. ---${NC}"
    echo "Puedes conectarte a la base de datos en el puerto 6379."
    echo "Puedes acceder a la interfaz gráfica en: http://<IP_DE_TU_SERVIDOR>:8001"
else
    echo -e "${RED}--- ¡Error! El contenedor de Redis no pudo iniciarse. ---${NC}"
    echo "Revisa los logs de Docker con: docker logs ecowatt-redis"
fi