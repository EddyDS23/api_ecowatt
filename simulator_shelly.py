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

# --- 2. CONFIGURACIÓN MQTT (Igual que tu .env) ---
MQTT_HOST = "134.209.61.74"
MQTT_PORT = 1883
MQTT_USER = "ecowatt_shelly"
MQTT_PASS = "SjTqQh4htnRK7rqN8tsOmSgFY"

# Topic de comandos (minúsculas siempre)
COMMAND_TOPIC = f"{DEVICE_MODEL}-{DEVICE_MAC.lower()}/rpc"

# --- 3. ESTADO INTERNO ---
device_state = {
    "ison": True,      # Empieza encendido
    "apower": 0.0,
    "voltage": 220.0,
    "current": 0.0
}

# --- FUNCIONES MQTT (CONTROL) ---
def on_connect(client, userdata, flags, rc):
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

        # Respuesta base
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

        # Enviar respuesta
        response["result"] = result
        client.publish(src, json.dumps(response))
        # print(f"   📤 Respuesta enviada")

    except Exception as e:
        print(f"❌ Error procesando mensaje: {e}")

# --- FUNCIONES HTTP (INGESTA DE DATOS) ---
def send_data_loop():
    """Bucle infinito que envía datos cada 5 segundos"""
    print("🚀 [HTTP] Iniciando envío de datos de consumo...")
    
    while True:
        try:
            # 1. Calcular valores según estado
            if device_state["ison"]:
                # Generar consumo simulado
                device_state["voltage"] = round(random.uniform(215.0, 225.0), 1)
                device_state["apower"] = round(random.uniform(500.0, 2500.0), 1) # Entre 500W y 2500W
                device_state["current"] = round(device_state["apower"] / device_state["voltage"], 2)
            else:
                # Si está apagado, todo a cero (pero voltaje se mantiene)
                device_state["apower"] = 0.0
                device_state["current"] = 0.0
                device_state["voltage"] = 220.0

            # 2. Preparar Payload (Formato Shelly)
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

            # 3. Enviar a la API
            # Nota: Si está apagado, enviamos 0W. Esto es IMPORTANTE para que 
            # la gráfica baje a 0 y no se quede "congelada" en el último valor alto.
            r = requests.post(API_URL, json=payload, timeout=2)
            
            if r.status_code == 200:
                status_icon = "🟢" if device_state["ison"] else "🔴"
                print(f"{status_icon} [DATA] Enviado: {device_state['apower']} W | {device_state['voltage']} V | {device_state['current']} A",flush=True)
            else:
                print(f"⚠️ [HTTP] Error {r.status_code}: {r.text}",flush=True)

        except Exception as e:
            print(f"❌ Error de conexión HTTP: {e}",flush=True)

        time.sleep(10) # Enviar cada 5 segundos

# --- MAIN ---
if __name__ == "__main__":
    # 1. Iniciar Cliente MQTT
    mqtt_client = mqtt.Client(client_id=f"sim_{DEVICE_MAC}_full")
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start() # Hilo separado para MQTT

        # 2. Iniciar Bucle de Datos en el hilo principal
        send_data_loop()

    except KeyboardInterrupt:
        print("\n🛑 Simulador detenido")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()