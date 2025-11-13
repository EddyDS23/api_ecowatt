# app/schemas/device_schema.py (VERSIÓN COMPLETA CORREGIDA)

from pydantic import BaseModel, Field, ConfigDict, field_validator

class BaseDevice(BaseModel):
    dev_hardware_id: str = Field(min_length=12, max_length=255)
    dev_name: str = Field(min_length=3, max_length=100)

class DeviceCreate(BaseDevice):
    pass

class DeviceUpdate(BaseModel):
    dev_name: str | None = Field(default=None, min_length=3, max_length=100)

class DeviceFCMRegister(BaseModel):
    """
    Schema para registrar token FCM desde React Native.
    El token FCM debe tener al menos 100 caracteres.
    """
    fcm_token: str = Field(
        ..., 
        min_length=100,
        max_length=255,
        description="Token FCM generado por Firebase en React Native"
    )
    
    @field_validator("fcm_token")
    @classmethod
    def validate_fcm_token(cls, v: str) -> str:
        """
        Valida que el token tenga formato correcto.
        """
        if not v or v.strip() == "":
            raise ValueError("Token FCM no puede estar vacío")
        
        if len(v) < 100:
            raise ValueError(
                f"Token FCM demasiado corto ({len(v)} caracteres). "
                "Tokens válidos tienen 100+ caracteres"
            )
        
        return v.strip()

class DeviceResponse(BaseDevice):
    dev_id: int
    dev_user_id: int
    dev_status: bool
    dev_brand: str | None
    dev_model: str | None
    model_config = ConfigDict(from_attributes=True)