# app/core/mqtt_client.py

import paho.mqtt.client as mqtt
import json
from typing import Dict, Any, Optional
from app.core import logger
from app.core.settings import settings  # Importamos tus settings
import uuid

class MQTTClient:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        
    def start(self):
        """Inicia la conexión usando las variables de tu .env"""
        try:
            # --- CORRECCIÓN AQUÍ ---
            # Generamos un ID único para cada worker de Gunicorn
            # Ej: ecowatt_backend_rpc_a1b2c3d4
            unique_id = f"ecowatt_backend_rpc_{uuid.uuid4().hex[:8]}"
            
            self.client = mqtt.Client(client_id=unique_id, clean_session=True)
            
            # Callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # CONEXIÓN
            logger.info(f"📡 Conectando Worker {unique_id} a MQTT...")
            
            self.client.connect(
                host=settings.MQTT_BROKER_HOST, 
                port=settings.MQTT_BROKER_PORT, 
                keepalive=60
            )
            
            self.client.loop_start() 
            
        except Exception as e:
            logger.error(f"❌ Error fatal iniciando MQTT: {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("🛑 Servicio MQTT detenido.")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            logger.info(f"✅ Backend conectado a Mosquitto ({settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT})")
        else:
            logger.error(f"❌ Fallo conexión MQTT, código: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        logger.warning(f"⚠️ MQTT Desconectado (Código {rc})")

    def publish_command(self, device_mac: str, method: str, params: Dict[str, Any]) -> bool:
        """Envía comandos al Shelly"""
        if not self.is_connected:
            logger.error("❌ No se puede enviar comando: MQTT desconectado")
            return False

        # Topic estándar: shellies/<MAC>/rpc
        topic = f"shellies/{device_mac}/rpc"
        
        payload = {
            "id": 1,
            "src": "ecowatt_backend",
            "method": method,
            "params": params
        }

        try:
            info = self.client.publish(topic, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=2.0)
            logger.info(f"📤 RPC Enviado a {device_mac}: {method}")
            return True
        except Exception as e:
            logger.error(f"❌ Error publicando mensaje: {e}")
            return False

# Instancia global
mqtt_client = MQTTClient()