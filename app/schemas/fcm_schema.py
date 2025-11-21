from pydantic import BaseModel, Field, field_validator

class FCMTokenRegister(BaseModel):
    """Schema para registrar token FCM"""
    fcm_token: str = Field(..., min_length=50, max_length=255)
    device_name: str | None = Field(None, max_length=100)
    platform: str | None = Field(None, max_length=20)
    
    @field_validator("fcm_token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 100:
            raise ValueError(f"Token FCM muy corto ({len(v)} caracteres)")
        return v
    
    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str | None) -> str | None:
        if v and v.lower() not in ['android', 'ios']:
            raise ValueError("Platform debe ser 'android' o 'ios'")
        return v.lower() if v else None