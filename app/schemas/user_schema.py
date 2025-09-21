from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field

class BaseUser(BaseModel):
    user_name:str = Field(min_length=5,max_length=100)
    user_email: EmailStr = Field(min_length=20, max_length=100)
    

class UserCreate(BaseUser):
     user_password: str = Field(min_length=8, max_length=30)

class UserUpdate(BaseModel):
     user_name:str|None  = Field(default=None,min_length=5,max_length=100)
     user_email: EmailStr | None = Field(default=None,min_length=20, max_length=100)

class UserChangePassword(BaseModel):
    user_password: str = Field(min_length=8, max_length=30)

class UserLogin(BaseModel):
    user_email:str = Field(min_length=10)
    user_password:str = Field(min_length=8,max_length=30)

class UserResponse(BaseUser):
    user_id:int 

    model_config = ConfigDict(from_attributes=True)