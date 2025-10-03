
from pydantic import BaseModel, ConfigDict
from datetime import datetime

class RecommendationResponse(BaseModel):
    rec_id: int
    rec_text: str
    rec_is_read: bool
    rec_created_at: datetime
    model_config = ConfigDict(from_attributes=True)