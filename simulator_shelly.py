# shelly_simulator.py
import requests
import time
import random

# --- CONFIGURACIÓN ---
# La URL de tu API en el servidor. Asegúrate de que sea la correcta.
API_INGEST_URL = "http://127.0.0.1:8000/api/v1/ingest/shelly"

# La dirección MAC de un dispositivo de prueba que YA hayas registrado en tu BD.
# Ve a tu tabla `tbdevice` y copia el `dev_hardware_id` de un dispositivo.
SHELLY_MAC_ADDRESS = "A1C4S2F2K1C1" # <-- ¡CAMBIA ESTO!

def generate_consumption_data():
    """Simula el consumo eléctrico fluctuante."""
    base_watts = random.uniform(100, 300) # Consumo base (standby)
    if 7 <= time.localtime().tm_hour < 10: # Pico de la mañana
        base_watts += random.uniform(500, 1500)
    if 19 <= time.localtime().tm_hour < 22: # Pico de la noche
        base_watts += random.uniform(800, 2000)

    voltage = random.uniform(120.0, 128.0)
    current = base_watts / voltage

    return {
        "watts": round(base_watts, 2),
        "volts": round(voltage, 2),
        "amps": round(current, 2)
    }

def send_data_to_api():
    """Construye el JSON y lo envía al endpoint de ingesta."""
    consumption = generate_consumption_data()

    # Este es el formato exacto del JSON que espera tu API
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
            print(f"✅ Datos enviados exitosamente: {consumption['watts']}W")
        else:
            print(f"❌ Error del servidor: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"🔥 Error de conexión: No se pudo conectar a la API. ¿Está corriendo? -> {e}")

if __name__ == "__main__":
    print("🚀 Iniciando simulador de Shelly...")
    print(f"Enviando datos a: {API_INGEST_URL}")
    print(f"Usando MAC: {SHELLY_MAC_ADDRESS}")

    if SHELLY_MAC_ADDRESS == "A1B2C3D4E5F6":
        print("\n⚠️ ADVERTENCIA: ¡No has cambiado la dirección MAC de prueba!")

    while True:
        send_data_to_api()
        time.sleep(10) # Envía datos cada 10 segundos
