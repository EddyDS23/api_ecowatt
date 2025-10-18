import time
import requests
from .settings import settings

# Diccionario para evitar enviar el mismo tipo de alerta muy seguido
_last_alert_time = {}
FLOOD_INTERVAL = 20  # segundos entre alertas iguales


def send_discord_alert(message: str, level: str = "INFO"):
    """
    Envía una alerta ligera a Discord con control de flood.
    Ideal para servidores con pocos recursos.
    """
    if not settings.DISCORD_WEBHOOK_URL:
        return

    now = time.time()
    last_time = _last_alert_time.get(level, 0)

    # Evita enviar mensajes iguales muy seguido
    if now - last_time < FLOOD_INTERVAL:
        return

    _last_alert_time[level] = now

    emoji = {
        "INFO": "ℹ️",
        "WARN": "⚠️",
        "ERROR": "🔥",
        "CRITICAL": "💀"
    }.get(level, "⚡")

    payload = {"content": f"{emoji} **[{level}] EcoWatt:** {message}"}

    try:
        requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=2)
    except Exception:
        pass
