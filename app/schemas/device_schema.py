# app/schemas/device_schema.py (ACTUALIZADO)

from pydantic import BaseModel, Field, ConfigDict

class BaseDevice(BaseModel):
    dev_hardware_id: str = Field(min_length=12, max_length=255)
    dev_name: str = Field(min_length=3, max_length=100)

class DeviceCreate(BaseDevice):
    pass

class DeviceUpdate(BaseModel):
    dev_name: str | None = Field(default=None, min_length=3, max_length=100)

class DeviceResponse(BaseDevice):
    dev_id: int
    dev_user_id: int
    dev_status: bool
    dev_brand: str | None
    dev_model: str | None
    model_config = ConfigDict(from_attributes=True)