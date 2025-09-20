from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field

class BaseClient(BaseModel):
    user_name:str = Field(min_length=5,max_length=100)
    user_email: EmailStr = Field(min_length=20, max_length=100)
    

class ClientCreate(BaseClient):
     user_password: str = Field(min_length=8, max_length=30)

class ClientUpdate(BaseModel):
     user_name:Optional[str]  = Field(min_length=5,max_length=100)
     user_email: Optional[EmailStr] = Field(min_length=20, max_length=100)

class ClientChangePassword(BaseModel):
    user_password: str = Field(min_length=8, max_length=30)

class ClientResponse(BaseClient):
    user_id:int 

    model_config = ConfigDict(from_attributes=True)