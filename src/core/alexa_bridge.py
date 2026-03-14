import paho.mqtt.client as mqtt
import json
import os
import sys

# Asegurar que encuentre los módulos internos
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.mqtt_manager import MQTTManager

class AlexaCloudBridge:
    def __init__(self, local_mqtt=None, on_mode_change=None):
        # Configuración Nube (HiveMQ)
        self.cloud_broker = "broker.hivemq.com"
        self.cloud_port = 1883
        self.cloud_topic = "john/yarvis/comandos"
        
        # Callback para notificar cambios de modo localmente
        self.on_mode_change = on_mode_change
        
        # Cliente local (Basado en el wrapper del proyecto)
        self.local_mqtt = local_mqtt or MQTTManager(client_id="Alexa_Local_Bridge")
        
        # Cliente Nube (Paho Puro)
        # Compatibilidad con Paho MQTT v2 (requiere CallbackAPIVersion)
        try:
            self.cloud_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"Yarvis_Cloud_Bridge_{os.urandom(2).hex()}")
        except AttributeError:
            # Fallback para Paho MQTT v1
            self.cloud_client = mqtt.Client(client_id=f"Yarvis_Cloud_Bridge_{os.urandom(2).hex()}")
            
        self.cloud_client.on_message = self.on_cloud_message
        self.cloud_client.on_connect = self.on_cloud_connect

    def on_cloud_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"[AlexaBridge] Conectado exitosamente a HiveMQ Cloud")
            client.subscribe(self.cloud_topic)
        else:
            print(f"[AlexaBridge] Error de conexión a HiveMQ: {rc}")

    def on_cloud_message(self, client, userdata, msg):
        """
        Recibe JSON estructurado o texto plano de Alexa y lo traduce al bus local
        """
        try:
            raw_payload = msg.payload.decode().strip()
            print(f"[AlexaBridge] MENSAJE CLOUD RECIBIDO: {raw_payload}")
            
            # Intentar parsear como JSON
            data = {}
            try:
                data = json.loads(raw_payload)
            except:
                # Fallback: soporte para formato "accion:dispositivo"
                if ":" in raw_payload:
                    parts = raw_payload.split(":", 1)
                    data = {"action": parts[0], "device": parts[1]}
                else:
                    data = {"action": "active", "device": raw_payload}

            accion_raw = data.get("action", "off").lower()
            dispositivo_raw = data.get("device", "desconocido").lower()

            # Normalización de acción: soportar "encend", "prend", "activ", "pon", "active"
            accion = "on" if any(x in accion_raw for x in ["encend", "prend", "activ", "pon", "active"]) else "off"
            
            # --- Respuesta de Agradecimiento a la Skill (Para evitar timeout) ---
            response_topic = "john/yarvis/respuestas"
            self.cloud_client.publish(response_topic, json.dumps({"status": "OK", "request": data.get("requestId", "unknown")}))
            
            # Mapeo de dispositivo Alexa -> Tópico y Actuador Local
            MAPEO_LOCAL = {
                "sala":    {"topic": "finca/cocina/comando", "actuator": "luces_sala",    "dtype": "esp32_kitchen"},
                "salon":   {"topic": "finca/cocina/comando", "actuator": "luces_sala",    "dtype": "esp32_kitchen"},
                "estancia":{"topic": "finca/cocina/comando", "actuator": "luces_sala",    "dtype": "esp32_kitchen"},
                "cocina":  {"topic": "finca/cocina/comando", "actuator": "luces_cocina",  "dtype": "esp32_kitchen"},
                "foco":    {"topic": "finca/cocina/comando", "actuator": "luces_cocina",  "dtype": "esp32_kitchen"},
                "cabinet": {"topic": "finca/cocina/comando", "actuator": "luces_cabinet", "dtype": "esp32_kitchen"},
                "gabinete":{"topic": "finca/cocina/comando", "actuator": "luces_cabinet", "dtype": "esp32_kitchen"},
                "isla":    {"topic": "finca/cocina/comando", "actuator": "luces_isla",    "dtype": "esp32_kitchen"},
                "barra":   {"topic": "finca/cocina/comando", "actuator": "luces_isla",    "dtype": "esp32_kitchen"},
                "sirena":  {"topic": "finca/seguridad/patio/siren/comando", "actuator": "accion", "dtype": "esp32_security"},
                "alarma":  {"topic": "finca/seguridad/patio/siren/comando", "actuator": "accion", "dtype": "esp32_security"},
                "luces":   {"topic": "finca/cocina/comando", "actuator": "todas_luces",  "dtype": "esp32_kitchen"} 
            }

            # --- NUEVA LÓGICA DE MODOS ROBUSTA ---
            MODO_NORM = {
                "manana": "Manana", "tarde": "Tarde", "noche": "Noche", 
                "dormir": "Dormir", "fiesta": "Fiesta", "mantenimiento": "Mantenimiento",
                "yoga": "Yoga", "estudio": "Estudio", "ninguno": "Ninguno",
                "tarde alegre": "Tarde Alegre", "noche romantica": "Noche Romantica",
                "seguridad maxima": "Seguridad Maxima"
            }

            es_comando_modo = (accion_raw == "set_mode" or 
                              "modo" in dispositivo_raw or 
                              dispositivo_raw in MODO_NORM or
                              "modo" in accion_raw)

            if es_comando_modo:
                mode_raw = data.get("mode", "").lower()
                if not mode_raw:
                    mode_raw = dispositivo_raw.replace("modo ", "").strip()
                
                mode = MODO_NORM.get(mode_raw, "Ninguno")
                if mode == "Ninguno":
                    for key, val in MODO_NORM.items():
                        if key in mode_raw or mode_raw in key:
                            mode = val
                            break

                print(f"[AlexaBridge] Solicitud de Modo: '{mode_raw}' -> '{mode}'")
                self.local_mqtt.publish("finca/sistema/modo", {"mode": mode})
                if self.on_mode_change:
                    self.on_mode_change(mode)
                return

            # Luces generales
            if "luces" in dispositivo_raw or "todo" in dispositivo_raw:
                for d in ["sala", "cocina", "isla", "cabinet"]:
                    info = MAPEO_LOCAL[d]
                    self.local_mqtt.publish(info["topic"], {info["actuator"]: accion})
                return

            # Dispositivo específico
            dispositivo_encontrado = False
            for keyword, info in MAPEO_LOCAL.items():
                if keyword in dispositivo_raw:
                    comando_local = {info["actuator"]: accion}
                    if self.local_mqtt.client.is_connected():
                        print(f"[AlexaBridge] Matching: '{keyword}' en '{dispositivo_raw}'. Enviando: {info['topic']}")
                        self.local_mqtt.publish(info["topic"], comando_local)
                        dispositivo_encontrado = True
                        break

            if not dispositivo_encontrado:
                print(f"[AlexaBridge] Dispositivo '{dispositivo_raw}' no reconocido.")

        except Exception as e:
            print(f"[AlexaBridge] Error procesando mensaje de la nube: {e}")

    def start(self):
        print("[AlexaBridge] Iniciando bridge con la nube...")
        try:
            # 1. Conexión Local (¡CRÍTICO!)
            if not self.local_mqtt.client.is_connected():
                if self.local_mqtt.connect():
                    print("[AlexaBridge] Conexión local establecida.")
                else:
                    print("[AlexaBridge] ADVERTENCIA: No se pudo establecer conexión local.")
            else:
                print("[AlexaBridge] Usando conexión local existente.")

            # 2. Configurar callbacks
            self.cloud_client.on_connect = self.on_cloud_connect
            self.cloud_client.on_message = self.on_cloud_message
            
            # 3. Conectar a HiveMQ Cloud
            print(f"[AlexaBridge] Intentando conectar a {self.cloud_broker}...")
            self.cloud_client.connect(self.cloud_broker, self.cloud_port)
            
            # 4. Iniciar loop en hilo separado
            self.cloud_client.loop_start()
            print("[AlexaBridge] Loop de la nube iniciado.")
        except Exception as e:
            print(f"[AlexaBridge] Error crítico al iniciar bridge: {e}")

    def stop(self):
        self.cloud_client.loop_stop()
        self.local_mqtt.disconnect()

if __name__ == "__main__":
    bridge = AlexaCloudBridge()
    bridge.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
