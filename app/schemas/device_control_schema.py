from pydantic import BaseModel, Field

class ControlSetRequest(BaseModel):
    """Request para forzar estado"""
    state: bool = Field(..., description="true=ON, false=OFF")

class ControlResponse(BaseModel):
    """Respuesta estándar de control"""
    success: bool
    message: str
    device_name: str | None = None
    method: str | None = None
    was_on: bool | None = None
    new_state: bool | None = None
    action: str | None = None
    error: str | None = None

class StatusResponse(BaseModel):
    """Respuesta de estado del switch"""
    success: bool
    device_name: str | None = None
    status: dict | None = None
    error: str | None = None