# app/schemas/monthly_report_schema.py

from pydantic import BaseModel
from datetime import date, datetime
from typing import List, Optional

# --- Encabezado del Reporte ---
class ReportHeader(BaseModel):
    period_month: str  # Ej: "Octubre 2025"
    user_name: str
    user_email: str
    billing_cycle_start: date
    billing_cycle_end: date
    monitored_circuits: List[str]  # Nombres de dispositivos

# --- Resumen Ejecutivo ---
class ExecutiveSummary(BaseModel):
    total_kwh_consumed: float
    total_estimated_cost_mxn: float
    carbon_footprint_kg: float
    equivalent_trees: float
    comparison_previous_month: Optional[dict] = None  # {"kwh_diff": +5.2, "cost_diff": +50.0, "percentage": +10}

# --- Detalles de Consumo ---
class DailyConsumptionPoint(BaseModel):
    date: date
    kwh: float

class ConsumptionDetails(BaseModel):
    daily_consumption: List[DailyConsumptionPoint]
    highest_consumption_day: DailyConsumptionPoint
    lowest_consumption_day: DailyConsumptionPoint
    average_daily_consumption: float

# --- Desglose de Costos ---
class TariffLevel(BaseModel):
    level_name: str  # "Básico", "Intermedio", "Excedente"
    kwh_consumed: float
    price_per_kwh: float
    subtotal_mxn: float

class CostBreakdown(BaseModel):
    applied_tariff: str  # Ej: "1F", "DAC"
    tariff_levels: List[TariffLevel]
    fixed_charge_mxn: float  # Solo para DAC
    total_cost_mxn: float

# --- Impacto Ambiental ---
class EnvironmentalImpact(BaseModel):
    total_co2_kg: float
    equivalent_trees_per_year: float
    comparison_note: Optional[str] = None

# --- Alertas del Mes ---
class MonthAlert(BaseModel):
    date: datetime
    title: str
    body: str

# --- Recomendaciones del Mes ---
class MonthRecommendation(BaseModel):
    date: datetime
    text: str

# --- REPORTE COMPLETO ---
class MonthlyReport(BaseModel):
    header: ReportHeader
    executive_summary: ExecutiveSummary
    consumption_details: ConsumptionDetails
    cost_breakdown: CostBreakdown
    environmental_impact: EnvironmentalImpact
    alerts: List[MonthAlert]
    recommendations: List[MonthRecommendation]
    generated_at: datetime

# --- Request para generar reporte ---
class GenerateReportRequest(BaseModel):
    month: int  # 1-12
    year: int   # Ej: 2025