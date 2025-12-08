import paho.mqtt.client as mqtt
import json
import time
import random
import requests
import threading

# --- 1. CONFIGURACIÓN DEL DISPOSITIVO ---
DEVICE_MODEL = "shellyplus1pm"  
DEVICE_MAC = "1a2b3c4a5b6c7d"     # ¡Asegúrate que coincida con tu BD!
API_URL = "https://core-cloud.dev/api/v1/ingest/shelly"

# --- 2. CONFIGURACIÓN MQTT ---
MQTT_HOST = "134.209.61.74"
MQTT_PORT = 1883
MQTT_USER = "ecowatt_shelly"
MQTT_PASS = "SjTqQh4htnRK7rqN8tsOmSgFY"

# Topic de comandos
COMMAND_TOPIC = f"{DEVICE_MODEL}-{DEVICE_MAC.lower()}/rpc"

# --- 3. ESTADO INTERNO ---
device_state = {
    "ison": True,
    "apower": 0.0,
    "voltage": 220.0,
    "current": 0.0
}

# --- FUNCIONES MQTT (CONTROL) ---

# 🔥 CORRECCIÓN AQUÍ: Agregamos 'properties=None' para compatibilidad con paho-mqtt v2
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ [MQTT] Conectado. Escuchando en: {COMMAND_TOPIC}")
        client.subscribe(COMMAND_TOPIC)
    else:
        print(f"❌ [MQTT] Error conexión: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        req_id = payload.get("id")
        method = payload.get("method")
        src = payload.get("src")
        params = payload.get("params", {})

        print(f"\n📨 [COMANDO RECIBIDO] {method}")

        response = {"id": req_id, "src": f"{DEVICE_MODEL}-{DEVICE_MAC.lower()}", "dst": src}
        result = {}

        if method == "Switch.Set":
            target = params.get("on", False)
            device_state["ison"] = target
            result = {"was_on": not target}
            print(f"   ⚙️ CAMBIO DE ESTADO: {'ON' if target else 'OFF'}")

        elif method == "Switch.Toggle":
            old_state = device_state["ison"]
            device_state["ison"] = not old_state
            result = {"was_on": old_state}
            print(f"   ⚙️ TOGGLE: {'ON' if device_state['ison'] else 'OFF'}")

        elif method == "Switch.GetStatus" or method == "Shelly.GetStatus":
            result = {
                "id": 0,
                "output": device_state["ison"],
                "apower": device_state["apower"],
                "voltage": device_state["voltage"],
                "current": device_state["current"],
                "temperature": {"tC": 45.0, "tF": 113.0}
            }

        elif method == "Sys.GetStatus":
             result = {
                 "mac": DEVICE_MAC,
                 "unixtime": int(time.time()),
                 "uptime": 999
             }

        response["result"] = result
        client.publish(src, json.dumps(response))

    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")

# --- FUNCIONES HTTP (INGESTA DE DATOS) ---
def send_data_loop():
    print("🚀 [HTTP] Iniciando envío de datos de consumo...")
    
    while True:
        try:
            # 1. Calcular valores
            if device_state["ison"]:
                device_state["voltage"] = round(random.uniform(215.0, 225.0), 1)
                device_state["apower"] = round(random.uniform(500.0, 2500.0), 1)
                device_state["current"] = round(device_state["apower"] / device_state["voltage"], 2)
            else:
                device_state["apower"] = 0.0
                device_state["current"] = 0.0
                device_state["voltage"] = 220.0

            # 2. Preparar Payload
            payload = {
                "switch:0": {
                    "id": 0,
                    "apower": device_state["apower"],
                    "voltage": device_state["voltage"],
                    "current": device_state["current"]
                },
                "sys": {
                    "mac": DEVICE_MAC
                }
            }

            print(f"\n📦 [PAYLOAD] Enviando JSON: {json.dumps(payload)}")

            # 3. Enviar a la API
            r = requests.post(API_URL, json=payload, timeout=2)
            
            if r.status_code == 200:
                status_icon = "🟢" if device_state["ison"] else "🔴"
                print(f"{status_icon} [API] Respuesta 200 OK")
            else:
                print(f"⚠️ [API] Error {r.status_code}: {r.text}")

        except Exception as e:
            print(f"❌ Error de conexión HTTP: {e}")

        time.sleep(5)

# --- MAIN ---
if __name__ == "__main__":
    unique_id = f"sim_{DEVICE_MAC}_{int(time.time())}"
    
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=unique_id)
    except:
        mqtt_client = mqtt.Client(client_id=unique_id)

    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start() 
        send_data_loop()

    except KeyboardInterrupt:
        print("\n🛑 Simulador detenido")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()