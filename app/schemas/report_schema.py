from pydantic import BaseModel, Field,ConfigDict, field_validator

from typing import List


class BaseReport(BaseModel):
    rep_total_kwh: float 
    rep_estimated_cost: float 

    # Validar y limitar a 2 decimales
    @field_validator("rep_total_kwh", "rep_estimated_cost", mode="before")
    def round_two_decimals(cls, v):
        return round(float(v), 2)
    

class CreateReport(BaseReport):
    rep_user_id:int = Field(gt=0)


class UpdateReport(BaseReport):
    rep_total_kwh: float | None = None
    rep_estimated_cost: float | None = None

    @field_validator("rep_total_kwh", "rep_estimated_cost", mode="before")
    def round_two_decimals(cls, v):
        if v is None:
            return v
        return round(float(v), 2)
    

class ReportResponse(BaseReport):
    rep_id:int 
    rep_user_id:int

    model_config = ConfigDict(from_attributes=True)