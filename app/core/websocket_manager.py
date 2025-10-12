from fastapi import WebSocket
from typing import List, Dict

class WebSocketManager:

    def __init__(self):
        self.active_connections:Dict[int,List[WebSocket]] = {}

    
    async def connect(self, device_id:int, websocket:WebSocket):
        '''Añade un nuevo dispositivo y lo añade a la lista de un dispositivo'''
        await websocket.accept()
        if device_id not in self.active_connections:
            self.active_connections[device_id] = []
        self.active_connections[device_id].append(websocket)

    def disconnect(self, device_id:int, websocket:WebSocket):
        '''Eliminar una conexion de la lista de un dispositivo'''
        if device_id not in self.active_connections:
            self.active_connections[device_id] = []
        self.active_connections[device_id].remove(websocket)

    async def broadcast_to_device(self, device_id:int, message:str):
        '''Envia un mensaje a todas las apps conectadas para un dispositivo especifico'''
        if device_id in self.active_connections:
            for connection in self.active_connections[device_id]:
                await connection.send_text(message)


manager = WebSocketManager()