# app/core/mqtt_client.py (MEJORADO)

import paho.mqtt.client as mqtt
import json
import uuid
import asyncio
from typing import Dict, Any, Optional
from app.core import logger
from app.core.settings import settings

class MQTTClient:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.is_connected = False
        # Diccionario para rastrear respuestas pendientes
        self.pending_responses: Dict[int, asyncio.Future] = {}
        
    def start(self):
        try:
            unique_id = f"ecowatt_backend_rpc_{uuid.uuid4().hex[:8]}"
            self.client = mqtt.Client(client_id=unique_id, clean_session=True)
            
            # Callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message  # 🆕 Añadido
            
            self.client.connect(
                host=settings.MQTT_BROKER_HOST, 
                port=settings.MQTT_BROKER_PORT, 
                keepalive=60
            )
            
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"❌ Error iniciando MQTT: {e}")

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            # 🆕 Suscribirse a respuestas de Shellies
            client.subscribe("shellies/+/rpc")
            logger.info(f"✅ Backend conectado a MQTT y suscrito a respuestas")
        else:
            logger.error(f"❌ Fallo conexión MQTT, código: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.is_connected = False
        logger.warning(f"⚠️ MQTT Desconectado (Código {rc})")

    def _on_message(self, client, userdata, msg):
        """🆕 Procesa respuestas RPC del Shelly"""
        try:
            payload = json.loads(msg.payload.decode())
            request_id = payload.get('id')
            
            if request_id in self.pending_responses:
                # Resolver el Future con la respuesta
                future = self.pending_responses.pop(request_id)
                if not future.done():
                    future.set_result(payload)
                    
        except Exception as e:
            logger.error(f"Error procesando mensaje MQTT: {e}")

    async def publish_command_async(
        self, 
        device_mac: str, 
        method: str, 
        params: Dict[str, Any],
        timeout: float = 5.0
    ) -> Dict:
        """
        🆕 Publica comando y espera respuesta del Shelly
        
        Returns:
            Dict con la respuesta del Shelly o error si timeout
        """
        if not self.is_connected:
            return {"success": False, "error": "MQTT desconectado"}

        # Generar ID único para rastrear respuesta
        request_id = int(uuid.uuid4().int & (1<<31)-1)
        
        topic = f"shellies/{device_mac}/rpc"
        payload = {
            "id": request_id,
            "src": "ecowatt_backend",
            "method": method,
            "params": params
        }

        try:
            # Crear Future para esperar respuesta
            future = asyncio.get_event_loop().create_future()
            self.pending_responses[request_id] = future
            
            # Publicar comando
            info = self.client.publish(topic, json.dumps(payload), qos=1)
            info.wait_for_publish(timeout=2.0)
            
            logger.info(f"📤 RPC Enviado a {device_mac}: {method} (ID: {request_id})")
            
            # Esperar respuesta con timeout
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                
                # Verificar si hay error en la respuesta
                if "error" in response:
                    error_msg = response["error"].get("message", "Error desconocido")
                    logger.error(f"❌ Shelly respondió con error: {error_msg}")
                    return {"success": False, "error": error_msg}
                
                logger.info(f"✅ Respuesta recibida de {device_mac}")
                return {
                    "success": True, 
                    "response": response.get("result", {}),
                    "message": "Comando ejecutado"
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout esperando respuesta de {device_mac}")
                self.pending_responses.pop(request_id, None)
                return {
                    "success": False, 
                    "error": "Timeout - El dispositivo no respondió"
                }
                
        except Exception as e:
            logger.error(f"❌ Error publicando: {e}")
            self.pending_responses.pop(request_id, None)
            return {"success": False, "error": str(e)}

# Instancia global
mqtt_client = MQTTClient()