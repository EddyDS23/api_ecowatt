
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class AlertResponse(BaseModel):
    ale_id: int
    ale_title: str
    ale_body: str
    ale_is_read: bool
    ale_created_at: datetime
    model_config = ConfigDict(from_attributes=True)