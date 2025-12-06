# shelly_high_consumption_simulator.py
import requests
import time
import random

# --- CONFIGURACIÓN ---
API_INGEST_URL = "https://core-cloud.dev/api/v1/ingest/shelly"
SHELLY_MAC_ADDRESS = "1b2b3b4b5b6b"  # MAC registrada en tu base de datos

# Intervalo entre envíos (en segundos)
SEND_INTERVAL = 10

def generate_high_consumption_data():
    """Genera consumo alto constante, independiente de la hora."""
    # Consumo alto entre 2000 W y 5000 W
    watts = random.uniform(2000, 5000)
    volts = random.uniform(120.0, 128.0)
    amps = watts / volts
    return {
        "watts": round(watts, 2),
        "volts": round(volts, 2),
        "amps": round(amps, 2)
    }

def send_data_to_api():
    """Envía los datos a la API."""
    consumption = generate_high_consumption_data()
    payload = {
        "switch:0": {
            "id": 0,
            "apower": consumption["watts"],
            "voltage": consumption["volts"],
            "current": consumption["amps"]
        },
        "sys": {
            "mac": SHELLY_MAC_ADDRESS
        }
    }
    try:
        response = requests.post(API_INGEST_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Datos enviados: {consumption['watts']} W")
        else:
            print(f"❌ Error del servidor: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"🔥 Error de conexión: {e}")

if __name__ == "__main__":
    print("🚀 Simulador de alto consumo iniciado...")
    print(f"Enviando datos cada {SEND_INTERVAL}s a: {API_INGEST_URL}")
    print(f"Usando MAC: {SHELLY_MAC_ADDRESS}")

    while True:
        send_data_to_api()
        time.sleep(SEND_INTERVAL)
