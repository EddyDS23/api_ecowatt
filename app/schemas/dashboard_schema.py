# app/schemas/dashboard_schema.py

from pydantic import BaseModel
from datetime import date

class CarbonFootprintData(BaseModel):
    co2_emitted_kg: float
    equivalent_trees_absorption_per_year: float

class DashboardSummary(BaseModel):
    kwh_consumed_cycle: float
    estimated_cost_mxn: float
    billing_cycle_start: date
    billing_cycle_end: date
    days_in_cycle: int
    current_tariff: str
    carbon_footprint: CarbonFootprintData 
    latest_recommendation: str | None = None
