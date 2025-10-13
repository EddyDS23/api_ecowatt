from pydantic import BaseModel
from typing import List, Tuple
from datetime import datetime
from enum import Enum

#Grafica de puntos individuales[timestamp, valor]
class HistoryDataPoints(BaseModel):
    timestamp: datetime
    value:float


#Respuesta que recibira el frontend
class HistoryResponse(BaseModel):
    period:str
    unit:str = "kWh"
    data_points: List[HistoryDataPoints]

#Periodos en los que se podra ver la grafica historica[diaria, semanal, mensual]
class HistoryPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"



