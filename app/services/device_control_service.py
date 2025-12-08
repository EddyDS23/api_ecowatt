# app/services/device_control_service.py

from sqlalchemy.orm import Session
from typing import Dict, Any
from app.repositories import DeviceRepository
from app.core import logger
from app.core.mqtt_client import mqtt_client

class DeviceControlService:
    def __init__(self, db: Session):
        self.db = db
        self.device_repo = DeviceRepository(db)

    async def toggle_device(self, device_id: int, user_id: int) -> Dict:
        """Invierte el estado del dispositivo (ON <-> OFF)"""
        return await self._send_mqtt_command(
            device_id=device_id, 
            user_id=user_id, 
            method="Switch.Toggle", 
            params={"id": 0}
        )

    async def set_state(self, device_id: int, user_id: int, turn_on: bool) -> Dict:
        """Fuerza el estado a Encendido (True) o Apagado (False)"""
        return await self._send_mqtt_command(
            device_id=device_id, 
            user_id=user_id, 
            method="Switch.Set", 
            params={"id": 0, "on": turn_on}
        )
    
    async def get_status(self, device_id: int, user_id: int) -> Dict:
        """Obtiene el estado completo del dispositivo en tiempo real"""
        return await self._send_mqtt_command(
            device_id=device_id,
            user_id=user_id,
            method="Switch.GetStatus",
            params={"id": 0}
        )

    async def _send_mqtt_command(self, device_id: int, user_id: int, method: str, params: dict) -> Dict:
        """
        Función central para enviar comandos.
        """
        # 1. Validar que el dispositivo exista
        device = self.device_repo.get_device_by_id_repository(device_id)
        
        if not device:
            return {"success": False, "error": "Dispositivo no encontrado"}
        
        # 2. Validar que el usuario sea el dueño
        if device.dev_user_id != user_id:
            logger.warning(f"⛔ Usuario {user_id} intentó controlar dispositivo ajeno {device_id}")
            return {"success": False, "error": "No autorizado"}

        # 3. Obtener datos MQTT
        device_mac = device.dev_hardware_id
        mqtt_prefix = device.dev_mqtt_prefix or "shellyplus1pm"

        # 4. Enviar la orden
        result = await mqtt_client.publish_command_async(
            device_mac=device_mac,
            mqtt_prefix=mqtt_prefix,
            method=method,
            params=params
        )
        
        # 5. Procesar resultado (AQUÍ ESTÁ EL CAMBIO)
        if result["success"]:
            
            # Datos base de la respuesta
            final_response = {
                "success": True,
                "message": "Comando ejecutado correctamente",
                "device_name": device.dev_name, # Agregamos el nombre para que no salga null
            }

            # Caso 1: GetStatus (Mapeamos 'response' -> 'status')
            if method == "Switch.GetStatus":
                final_response["status"] = result.get("response", {})
                return final_response

            # Caso 2: Switch.Set / Toggle (Mapeamos datos específicos)
            elif method in ["Switch.Set", "Switch.Toggle"]:
                 final_response["result_data"] = result.get("response", {})
                 return final_response
            
            # Caso 3: Otros métodos (Devolvemos genérico)
            else:
                return result

        else:
            return {
                "success": False, 
                "error": result.get("error", "Error desconocido en comunicación MQTT")
            }