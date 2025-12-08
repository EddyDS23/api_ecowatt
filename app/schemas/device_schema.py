# app/schemas/device_schema.py (VERSIÓN COMPLETA CORREGIDA)

from pydantic import BaseModel, Field, ConfigDict, field_validator

class BaseDevice(BaseModel):
    dev_hardware_id: str = Field(min_length=12, max_length=255)
    dev_name: str = Field(min_length=3, max_length=100)
    dev_mqtt_prefix: str | None = Field(default="shellyplus1pm")

class DeviceCreate(BaseDevice):
    pass

class DeviceUpdate(BaseModel):
    dev_name: str | None = Field(default=None, min_length=3, max_length=100)
    dev_mqtt_prefix: str | None = None

class DeviceResponse(BaseDevice):
    dev_id: int
    dev_user_id: int
    dev_status: bool
    dev_brand: str | None
    dev_model: str | None
    dev_mqtt_prefix: str
    model_config = ConfigDict(from_attributes=True)