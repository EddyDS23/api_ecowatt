from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class BaseDevice(BaseModel):
    
    dev_brand:str = Field(min_length=1,max_length=200)
    dev_model:str = Field(min_length=1, max_length=200)
    dev_endpoint_url:str = Field(min_length=10) 

class DeviceCreate(BaseDevice):
    dev_user_id:int = Field(gt=0)
  
    

class DeviceUpdate(BaseModel):
    dev_brand:Optional[str] = Field(min_length=1,max_length=200)
    dev_model:Optional[str] = Field(min_length=1, max_length=200)
    dev_endpoint_url:str = Field(min_length=10) 

class DeviceResponse(BaseDevice):
    dev_id:int
    dev_user_id:int

    model_config = ConfigDict(from_attributes=True)

