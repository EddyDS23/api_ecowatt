# app/services/device_control_service.py

from sqlalchemy.orm import Session
from typing import Dict
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

    async def _send_mqtt_command(self, device_id: int, user_id: int, method: str, params: dict) -> Dict:
        # 1. Validar que el dispositivo exista
        device = self.device_repo.get_device_by_id_repository(device_id)
        
        if not device:
            return {"success": False, "error": "Dispositivo no encontrado"}
        
        # 2. Validar que el usuario sea el dueño
        if device.dev_user_id != user_id:
            logger.warning(f"⛔ Usuario {user_id} intentó controlar dispositivo ajeno {device_id}")
            return {"success": False, "error": "No autorizado"}

        # 3. Obtener la MAC para el Topic
        # OJO: Esto asume que en tu BD guardas "shellyplus1pm-AABBCC" o solo la MAC "AABBCC".
        # El mqtt_client.py que te pasé antes usa f"shellies/{device_mac}/rpc".
        # Asegúrate que coincida.
        device_mac = device.dev_hardware_id

        # 4. Enviar la orden al Broker
        success = mqtt_client.publish_command(
            device_mac=device_mac,
            method=method,
            params=params
        )

        if success:
            # Respuesta optimista para que la App se sienta rápida
            return {
                "success": True, 
                "message": "Comando enviado", 
                "target_state": params.get("on", "toggle")
            }
        else:
            return {
                "success": False, 
                "error": "Error de conexión interna con MQTT"
            }