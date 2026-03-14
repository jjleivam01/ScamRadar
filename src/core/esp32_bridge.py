import asyncio
import websockets
import json
import os
import sys

# Rutas para importar módulos core
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.mqtt_manager import MQTTManager

class ESP32SecurityBridge:
    def __init__(self, ws_port=81):
        self.ws_port = ws_port
        self.mqtt = MQTTManager(client_id="ESP32_Security_Bridge")
        self.connected_clients = set()

    def on_mqtt_message(self, topic, payload):
        """Manejador de comandos MQTT -> WebSocket"""
        print(f"[Bridge] Comando MQTT recibido en {topic}: {payload}")
        
        # Tópico esperado: finca/seguridad/patio/[id]/comando
        parts = topic.split('/')
        if len(parts) >= 4:
            device_id = parts[3]
            action = payload.get("accion", "off")
            
            # Construir mensaje para el ESP32
            ws_msg = {
                "type": "command",
                "id": device_id,
                "action": action
            }
            
            # Enviar a todos los ESP32 conectados (usualmente solo habrá uno)
            asyncio.run_coroutine_threadsafe(self.broadcast_ws(ws_msg), asyncio.get_event_loop())

    async def broadcast_ws(self, data):
        if not self.connected_clients:
            return
        
        message = json.dumps(data)
        await asyncio.gather(*[client.send(message) for client in self.connected_clients])

    async def handle_ws(self, websocket, path):
        """Manejador de mensajes WebSocket ESP32 -> MQTT"""
        self.connected_clients.add(websocket)
        print(f"[Bridge] ESP32 conectado desde {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "identification":
                        print(f"[Bridge] Dispositivo identificado: {data.get('device_type')}")
                        self.mqtt.publish("finca/seguridad/patio/config", data)
                        
                    elif msg_type == "state_report":
                        # Publicar el estado a MQTT
                        states = data.get("state", {})
                        print(f"[Bridge] Reporte de estado: {states}")
                        self.mqtt.publish("finca/seguridad/patio/estado", states)
                        
                        # Alertas específicas para el Master Agent
                        for sensor_id, status in states.items():
                            if status == "active" and sensor_id != "siren":
                                alert_msg = {
                                    "agente": "SecurityBridge",
                                    "alerta": f"Movimiento detectado en {sensor_id}",
                                    "nivel": "CRITICAL"
                                }
                                self.mqtt.publish("finca/seguridad/alertas", alert_msg)
                    
                    elif msg_type == "heartbeat":
                        self.mqtt.publish("finca/seguridad/patio/heartbeat", {"uptime": data.get("uptime")})

                except Exception as e:
                    print(f"[Bridge] Error procesando mensaje WS: {e}")
        
        except websockets.ConnectionClosed:
            print("[Bridge] ESP32 desconectado.")
        finally:
            self.connected_clients.remove(websocket)

    async def start(self):
        # Conectar a MQTT
        self.mqtt.on_message_callback = self.on_mqtt_message
        if self.mqtt.connect():
            self.mqtt.subscribe("finca/seguridad/patio/+/comando")
            
            print(f"[Bridge] Servidor WebSocket de Seguridad iniciado en el puerto {self.ws_port}")
            async with websockets.serve(self.handle_ws, "0.0.0.0", self.ws_port):
                await asyncio.Future()  # Correr para siempre

if __name__ == "__main__":
    bridge = ESP32SecurityBridge()
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        print("[Bridge] Apagando...")
