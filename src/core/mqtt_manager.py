import paho.mqtt.client as mqtt
import json
import time

class MQTTManager:
    def __init__(self, broker="localhost", port=1883, client_id="YarvisEdgeManager"):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        # Compatibilidad con paho-mqtt v2.0+
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)
        
        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.on_message_callback = None

    def _on_connect(self, *args, **kwargs):
        reason_code = args[3] if len(args) > 3 else kwargs.get("reasonCode") or kwargs.get("rc")
        if reason_code == 0 or reason_code == "Success":
            # print(f"[MQTT] Conectado exitosamente al broker {self.broker}")
            pass
        else:
            print(f"[MQTT] Error de conexión, código: {reason_code}")

    def _on_message(self, *args, **kwargs):
        try:
            msg = args[2] if len(args) > 2 else kwargs.get("message")
            if hasattr(msg, "payload") and hasattr(msg, "topic"):
                # print(f"[MQTT CORE] Recibido: {msg.topic}")
                payload = json.loads(msg.payload.decode())
                if self.on_message_callback:
                    self.on_message_callback(msg.topic, payload)
        except Exception as e:
            topic = getattr(msg, "topic", "unknown") if 'msg' in locals() else "unknown"
            print(f"[MQTT] Error procesando mensaje en {topic}: {e}")

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"[MQTT] No se pudo conectar al broker: {e}")
            return False

    def subscribe(self, topic):
        self.client.subscribe(topic)
        print(f"[MQTT] Suscrito a: {topic}")

    def publish(self, topic, data):
        payload = json.dumps(data)
        self.client.publish(topic, payload)
        # Opcional: print log para telemetría interna
        # print(f"[MQTT] Publicado en {topic}: {payload}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    # Test simple
    manager = MQTTManager()
    if manager.connect():
        manager.publish("finca/test", {"status": "online", "message": "Yarvis MQTT Manager Ready"})
        time.sleep(2)
        manager.disconnect()
