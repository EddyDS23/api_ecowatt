# app/schemas/user_schema.py (ACTUALIZADO)

from pydantic import BaseModel, EmailStr, ConfigDict, Field

class BaseUser(BaseModel):
    user_name: str = Field(min_length=5, max_length=100)
    user_email: EmailStr
    user_trf_rate: str = Field(min_length=1, max_length=10)
    user_billing_day: int = Field(gt=0, lt=32, default=1) # <-- CAMPO AÑADIDO

class UserCreate(BaseUser):
     user_password: str = Field(min_length=8, max_length=30)

class UserUpdate(BaseModel):
     user_name: str | None = Field(default=None, min_length=5, max_length=100)
     user_email: EmailStr | None = Field(default=None)
     user_trf_rate: str | None = Field(default=None, min_length=1, max_length=10)
     user_billing_day: int | None = Field(default=None, gt=0, lt=32)

class UserChangePassword(BaseModel):
    user_password: str = Field(min_length=8, max_length=30)

class UserResponse(BaseUser):
    user_id: int
    model_config = ConfigDict(from_attributes=True)