# app/schemas/ingest_schema.py 

from pydantic import BaseModel, Field

# Modelo para la sección "switch:0" del JSON del Shelly
class ShellySwitchStatus(BaseModel):
    id: int
    apower: float   
    voltage: float  
    current: float  

# Modelo para la sección "sys" del JSON del Shelly
class ShellySysStatus(BaseModel):
    mac: str

# El modelo principal que representa todo el cuerpo de la petición
class ShellyIngestData(BaseModel):
    switch_status: ShellySwitchStatus = Field(..., alias="switch:0")
    sys_status: ShellySysStatus = Field(..., alias="sys")