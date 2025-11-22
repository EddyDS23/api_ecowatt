# app/services/report_service.py

from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import calendar

from app.repositories import UserRepository, TarrifRepository, AlertRepository, RecommendationRepository, ReportRepository
from app.schemas.monthly_report_schema import MonthlyReport, ReportHeader, ExecutiveSummary, ConsumptionDetails, CostBreakdown, EnvironmentalImpact, MonthAlert, MonthRecommendation, DailyConsumptionPoint, TariffLevel
from app.core import logger, settings


def generate_monthly_report(db: Session, redis_client: Redis, user_id: int, month: int, year: int) -> MonthlyReport | None:
    """
    Genera reporte mensual.
    
    ✅ LÓGICA:
    - Mes actual: genera desde Redis (no guarda)
    - Mes anterior: busca en BD primero, si no existe lo genera y guarda
    """
    try:
        now = datetime.now(timezone.utc)
        is_current_month = (month == now.month and year == now.year)
        
        report_repo = ReportRepository(db)
        
        # ✅ Mes actual: generar sin guardar
        if is_current_month:
            logger.info(f"📊 Generando reporte MES ACTUAL: {month}/{year} (tiempo real)")
            return _generate_report_from_redis(db, redis_client, user_id, month, year)
        
        # ✅ Mes anterior: buscar en BD
        logger.info(f"🔍 Buscando reporte guardado: {month}/{year}")
        existing = report_repo.get_by_month(user_id, month, year)
        
        if existing:
            logger.info(f"✅ Reporte encontrado en BD")
            return MonthlyReport(**existing.mr_report_data)
        
        # ✅ No existe: generarlo y guardarlo
        logger.info(f"⚙️  Generando y guardando reporte: {month}/{year}")
        report = _generate_report_from_redis(db, redis_client, user_id, month, year)
        
        if report:
            report_repo.save(
                user_id=user_id,
                month=month,
                year=year,
                report_data=report.model_dump(mode='json'),
                total_kwh=float(report.executive_summary.total_kwh_consumed),
                total_cost=float(report.executive_summary.total_estimated_cost_mxn)
            )
        
        return report
        
    except Exception as e:
        logger.exception(f"Error generando reporte: {e}")
        return None
    

def _generate_report_from_redis(db: Session, redis_client: Redis, user_id: int, month: int, year: int) -> MonthlyReport | None:
    """
    Genera reporte desde Redis/PostgreSQL.
    """
    try:
        
        logger.info(f"📄 Generando reporte mensual para user {user_id} - {month}/{year}")
        
        # 1. Obtener usuario y validar
        user_repo = UserRepository(db)
        user = user_repo.get_user_id_repository(user_id)
        if not user:
            logger.error(f"Usuario {user_id} no encontrado")
            return None
        
        # 2. Calcular ciclo de facturación del mes solicitado
        billing_cycle = _calculate_billing_cycle_for_month(user.user_billing_day, month, year)
        if not billing_cycle:
            logger.error(f"No se pudo calcular ciclo de facturación para {month}/{year}")
            return None
        
        start_date, end_date = billing_cycle
        logger.info(f"   Ciclo de facturación: {start_date} → {end_date}")
        
        # 3. Obtener dispositivos activos
        active_devices = [d for d in user.devices if d.dev_status]
        if not active_devices:
            logger.warning(f"Usuario {user_id} no tiene dispositivos activos")
            return None
        
        # 4. Generar cada sección del reporte
        header = _generate_header(user, active_devices, start_date, end_date, month, year)
        
        daily_consumption = _get_daily_consumption_from_redis(
            redis_client, user_id, active_devices, start_date, end_date
        )
        
        total_kwh = sum(point.kwh for point in daily_consumption)
        logger.info(f"   Total kWh consumidos: {total_kwh:.2f}")
        
        consumption_details = _generate_consumption_details(daily_consumption, start_date, end_date)
        
        cost_breakdown = _calculate_cost_breakdown(db, user, total_kwh, start_date.date())
        
        executive_summary = _generate_executive_summary(
            total_kwh, cost_breakdown.total_cost_mxn, db, user_id, month, year
        )
        
        environmental_impact = _calculate_environmental_impact(total_kwh)
        
        alerts = _get_month_alerts(db, user_id, start_date, end_date)
        
        recommendations = _get_month_recommendations(db, user_id, start_date, end_date)
        
        # 5. Construir reporte completo
        report = MonthlyReport(
            header=header,
            executive_summary=executive_summary,
            consumption_details=consumption_details,
            cost_breakdown=cost_breakdown,
            environmental_impact=environmental_impact,
            alerts=alerts,
            recommendations=recommendations,
            generated_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"✅ Reporte mensual generado exitosamente para user {user_id}")
        return report
        
    except Exception as e:
        logger.exception(f"Error en _generate_report_from_redis: {e}")
        return None


def _calculate_billing_cycle_for_month(billing_day: int, month: int, year: int) -> tuple | None:
    """Calcula las fechas de inicio y fin del ciclo de facturación para un mes específico"""
    try:
        # Crear fecha del inicio del ciclo EN UTC
        try:
            cycle_start = datetime(year, month, billing_day, 0, 0, 0, tzinfo=timezone.utc)
        except ValueError:
            # Si el día no existe en el mes (ej: 31 en febrero), usar último día del mes
            last_day = calendar.monthrange(year, month)[1]
            cycle_start = datetime(year, month, min(billing_day, last_day), 0, 0, 0, tzinfo=timezone.utc)
        
        # Fin del ciclo: un mes después, menos 1 segundo
        cycle_end = (cycle_start + relativedelta(months=1)) - timedelta(seconds=1)
        
        return (cycle_start, cycle_end)
    except Exception as e:
        logger.error(f"Error calculando ciclo: {e}")
        return None


def _generate_header(user, devices, start_date, end_date, month, year) -> ReportHeader:
    """Genera el encabezado del reporte"""
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    return ReportHeader(
        period_month=f"{month_names[month]} {year}",
        user_name=user.user_name,
        user_email=user.user_email,
        billing_cycle_start=start_date.date(),
        billing_cycle_end=end_date.date(),
        monitored_circuits=[d.dev_name for d in devices]
    )


def _get_daily_consumption_from_redis(redis_client: Redis, user_id: int, devices, start_date, end_date) -> list:
    """Obtiene el consumo diario de Redis para el periodo especificado"""
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    # Diccionario para acumular mediciones por día
    daily_measurements = defaultdict(list)
    
    # Procesar cada dispositivo
    for device in devices:
        watts_key = f"ts:user:{user_id}:device:{device.dev_id}:watts"
        
        try:
            if not redis_client.exists(watts_key):
                logger.warning(f"Key no existe: {watts_key}")
                continue
            
            # Obtener todos los puntos del periodo
            data = redis_client.ts().range(watts_key, start_ts, end_ts)
            logger.info(f"   Device {device.dev_id}: {len(data)} puntos obtenidos")
            
            # Agrupar por fecha
            for ts, value in data:
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                date_str = dt.strftime("%Y-%m-%d")
                daily_measurements[date_str].append({
                    "timestamp": ts,
                    "watts": float(value)
                })
        except Exception as e:
            logger.error(f"Error obteniendo datos de {watts_key}: {e}")
            continue
    
    # Calcular kWh por día
    daily_consumption = []
    current_date = start_date.date()
    
    while current_date <= end_date.date():
        date_str = current_date.strftime("%Y-%m-%d")
        measurements = daily_measurements.get(date_str, [])
        
        if not measurements:
            kwh = 0.0
        else:
            # Calcular kWh usando integración trapezoidal
            measurements.sort(key=lambda x: x["timestamp"])
            total_watt_seconds = 0.0
            
            for i in range(1, len(measurements)):
                t0 = measurements[i-1]["timestamp"]
                t1 = measurements[i]["timestamp"]
                w0 = measurements[i-1]["watts"]
                w1 = measurements[i]["watts"]
                
                dt_seconds = (t1 - t0) / 1000.0
                avg_watts = (w0 + w1) / 2.0
                total_watt_seconds += avg_watts * dt_seconds
            
            kwh = total_watt_seconds / 3_600_000.0
        
        daily_consumption.append(DailyConsumptionPoint(
            date=current_date,
            kwh=round(kwh, 4)
        ))
        
        current_date += timedelta(days=1)
    
    return daily_consumption


def _generate_consumption_details(daily_consumption: list, start_date, end_date) -> ConsumptionDetails:
    """Genera los detalles de consumo con estadísticas"""
    if not daily_consumption:
        return ConsumptionDetails(
            daily_consumption=[],
            highest_consumption_day=DailyConsumptionPoint(date=start_date.date(), kwh=0.0),
            lowest_consumption_day=DailyConsumptionPoint(date=start_date.date(), kwh=0.0),
            average_daily_consumption=0.0
        )
    
    # Encontrar día de mayor y menor consumo
    highest = max(daily_consumption, key=lambda x: x.kwh)
    lowest = min(daily_consumption, key=lambda x: x.kwh)
    
    # Calcular promedio diario
    total_kwh = sum(point.kwh for point in daily_consumption)
    days_in_cycle = (end_date.date() - start_date.date()).days + 1
    average = total_kwh / days_in_cycle if days_in_cycle > 0 else 0.0
    
    return ConsumptionDetails(
        daily_consumption=daily_consumption,
        highest_consumption_day=highest,
        lowest_consumption_day=lowest,
        average_daily_consumption=round(average, 4)
    )


def _calculate_cost_breakdown(db: Session, user, total_kwh: float, target_date) -> CostBreakdown:
    """Calcula el desglose detallado de costos por niveles tarifarios"""
    tariff_repo = TarrifRepository(db)
    tariffs = tariff_repo.get_tariffs_for_date(user.user_trf_rate, target_date)
    
    if not tariffs:
        logger.error(f"No se encontraron tarifas para {user.user_trf_rate}")
        return CostBreakdown(
            applied_tariff=user.user_trf_rate,
            tariff_levels=[],
            fixed_charge_mxn=0.0,
            total_cost_mxn=0.0
        )
    
    tariff_levels = []
    total_cost = 0.0
    kwh_remaining = total_kwh
    fixed_charge = 0.0
    
    # Cargo fijo para DAC
    if user.user_trf_rate == "DAC" and hasattr(tariffs[0], 'trf_fixed_charge_mxn'):
        fixed_charge = float(tariffs[0].trf_fixed_charge_mxn or 0.0)
        total_cost += fixed_charge
    
    # Calcular por cada nivel
    for tariff in tariffs:
        if kwh_remaining <= 0:
            break
        
        # Calcular límite del nivel
        lower_limit = tariff.trf_lower_limit_kwh or 0
        upper_limit = tariff.trf_upper_limit_kwh or float('inf')
        tier_capacity = upper_limit - lower_limit
        
        # kWh consumidos en este nivel
        kwh_in_tier = min(kwh_remaining, tier_capacity)
        
        # Costo del nivel
        price_per_kwh = float(tariff.trf_price_per_kwh)
        subtotal = kwh_in_tier * price_per_kwh
        
        tariff_levels.append(TariffLevel(
            level_name=tariff.trf_level_name,
            kwh_consumed=round(kwh_in_tier, 2),
            price_per_kwh=price_per_kwh,
            subtotal_mxn=round(subtotal, 2)
        ))
        
        total_cost += subtotal
        kwh_remaining -= kwh_in_tier
    
    return CostBreakdown(
        applied_tariff=user.user_trf_rate,
        tariff_levels=tariff_levels,
        fixed_charge_mxn=round(fixed_charge, 2),
        total_cost_mxn=round(total_cost, 2)
    )


def _generate_executive_summary(total_kwh: float, total_cost: float, db: Session, 
                                user_id: int, month: int, year: int) -> ExecutiveSummary:
    """Genera el resumen ejecutivo con comparativa del mes anterior (si existe)"""
    co2_kg = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
    trees = co2_kg / 22
    
    # TODO: Implementar comparativa con mes anterior
    # Esto requeriría guardar reportes previos o consultar Redis para el mes anterior
    comparison = None
    
    return ExecutiveSummary(
        total_kwh_consumed=round(total_kwh, 2),
        total_estimated_cost_mxn=round(total_cost, 2),
        carbon_footprint_kg=round(co2_kg, 2),
        equivalent_trees=round(trees, 4),
        comparison_previous_month=comparison
    )


def _calculate_environmental_impact(total_kwh: float) -> EnvironmentalImpact:
    """Calcula el impacto ambiental"""
    co2_kg = total_kwh * settings.CARBON_EMISSION_FACTOR_KG_PER_KWH
    trees = co2_kg / 22
    
    return EnvironmentalImpact(
        total_co2_kg=round(co2_kg, 2),
        equivalent_trees_per_year=round(trees, 4),
        comparison_note="Promedio nacional/regional no disponible aún"
    )


def _get_month_alerts(db: Session, user_id: int, start_date, end_date) -> list:
    """Obtiene las alertas del mes"""
    alert_repo = AlertRepository(db)
    alerts = alert_repo.get_alerts_by_user(user_id)
    
    # Filtrar alertas del periodo
    month_alerts = []
    for alert in alerts:
        # Asegurar que la fecha tenga timezone UTC
        alert_date = alert.ale_created_at
        if not alert_date.tzinfo:
            alert_date = alert_date.replace(tzinfo=timezone.utc)
        
        if start_date <= alert_date <= end_date:
            month_alerts.append(MonthAlert(
                date=alert.ale_created_at,
                title=alert.ale_title,
                body=alert.ale_body
            ))
    
    logger.info(f"   Alertas del mes: {len(month_alerts)}")
    return month_alerts


def _get_month_recommendations(db: Session, user_id: int, start_date, end_date) -> list:
    """Obtiene las recomendaciones del mes"""
    rec_repo = RecommendationRepository(db)
    recommendations = rec_repo.get_recommendations_by_user(user_id)
    
    # Filtrar recomendaciones del periodo
    month_recs = []
    for rec in recommendations:
        # Asegurar que la fecha tenga timezone UTC
        rec_date = rec.rec_created_at
        if not rec_date.tzinfo:
            rec_date = rec_date.replace(tzinfo=timezone.utc)
        
        if start_date <= rec_date <= end_date:
            month_recs.append(MonthRecommendation(
                date=rec.rec_created_at,
                text=rec.rec_text
            ))
    
    logger.info(f"   Recomendaciones del mes: {len(month_recs)}")
    return month_recs