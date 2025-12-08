# app/core/mqtt_client.py

import paho.mqtt.client as mqtt
import json
import uuid
import asyncio
from typing import Dict, Any, Optional
from app.core import logger
from app.core.settings import settings

# Topic único donde el backend escuchará TODAS las respuestas
BACKEND_RESPONSE_TOPIC = "ecowatt/backend/rpc_response"

class MQTTClient:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        self.pending_responses: Dict[int, asyncio.Future] = {}
        
    def start(self):
        try:
            unique_id = f"ecowatt_core_{uuid.uuid4().hex[:8]}"
            self.client = mqtt.Client(client_id=unique_id, clean_session=True)
            
            # Autenticación (si aplica)
            if hasattr(settings, 'MQTT_SHELLY_USER') and settings.MQTT_SHELLY_USER:
                self.client.username_pw_set(
                    settings.MQTT_SHELLY_USER,
                    settings.MQTT_SHELLY_PASS
                )
            
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message 
            
            self.client.connect(
                host=settings.MQTT_BROKER_HOST, 
                port=settings.MQTT_BROKER_PORT, 
                keepalive=60
            )
            self.client.loop_start()
            logger.info("🚀 MQTT Client iniciado")
            
        except Exception as e:
            logger.error(f"❌ Error iniciando MQTT: {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            # Nos suscribimos SOLAMENTE a nuestro canal de retorno
            client.subscribe(BACKEND_RESPONSE_TOPIC)
            logger.info(f"✅ Conectado a MQTT. Escuchando en: {BACKEND_RESPONSE_TOPIC}")
        else:
            logger.error(f"❌ Fallo conexión MQTT, código: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        logger.warning(f"⚠️ MQTT Desconectado (Código {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            request_id = payload.get('id')
            
            if request_id in self.pending_responses:
                future = self.pending_responses.pop(request_id)
                if not future.done():
                    future.set_result(payload)
                    
        except Exception as e:
            logger.error(f"Error procesando mensaje MQTT: {e}")

    async def publish_command_async(
        self, 
        device_mac: str, 
        mqtt_prefix: str,  # <--- RECIBIMOS EL PREFIJO
        method: str, 
        params: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict:
        """
        Envía comando a cualquier Shelly Gen2/3 usando su prefijo específico.
        """
        if not self.is_connected:
            return {"success": False, "error": "MQTT Backend desconectado"}

        request_id = int(uuid.uuid4().int & (1<<31)-1)
        
        # 1. Construcción dinámica del Topic (siempre minúsculas)
        # Ej: shellyplus2pm-a80324b1c2/rpc
        topic = f"{mqtt_prefix}-{device_mac.lower()}/rpc"
        
        # 2. Payload RPC con instrucción de respuesta
        payload = {
            "id": request_id,
            "src": BACKEND_RESPONSE_TOPIC,  # <--- MAGIA: Le deci   mos que responda AQUÍ
            "method": method,
            "params": params
        }

        try:
            future = asyncio.get_event_loop().create_future()
            self.pending_responses[request_id] = future
            
            info = self.client.publish(topic, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=2.0)
            
            logger.info(f"📤 RPC → {topic}: {method}")
            
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                
                if "error" in response:
                    error_msg = response["error"].get("message", "Error desconocido")
                    logger.error(f"❌ Shelly Error ({device_mac}): {error_msg}")
                    return {"success": False, "error": error_msg}
                
                return {
                    "success": True, 
                    "response": response.get("result", {}),
                    "message": "Comando ejecutado"
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout RPC ({device_mac})")
                self.pending_responses.pop(request_id, None)
                return {"success": False, "error": "Dispositivo no responde (Timeout)"}
                
        except Exception as e:
            logger.error(f"❌ Error crítico MQTT: {e}")
            self.pending_responses.pop(request_id, None)
            return {"success": False, "error": str(e)}

# Instancia global
mqtt_client = MQTTClient()