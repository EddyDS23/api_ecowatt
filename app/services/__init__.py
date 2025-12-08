# app/services/__init__.py 

# Auth Service
from .auth_service import login_for_access_token, refresh_access_token, logout_user, request_password_reset, reset_password

# User Service
from .user_service import get_user_by_id_service, create_user_service, update_user_service

# Device Service
from .device_service import (
    get_device_by_id_service,
    get_all_devices_by_user_service,
    create_device_service,
    update_device_service,
    delete_device_service,
    change_device_status_service
)

from .ingest_service import(
    process_shelly_data
)

from .dashboard_service import get_dashboard_summary

from .history_service import get_history_data, get_last_7_days_data

from .analysis_service import analyze_consumption_patterns

# Nuevos servicios (solo lectura por ahora)
from .alert_service import get_alerts_by_user_service
from .recommendation_service import get_recommendations_by_user_service


from .report_service import generate_monthly_report
