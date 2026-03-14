import asyncio
import httpx
import logging
import json
import time
from typing import Dict, Any

from src.core.mqtt_manager import MQTTManager

logger = logging.getLogger(__name__)

class ESPManager:
    def __init__(self, ping_interval: int = 5, timeout: int = 3):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.ping_interval = ping_interval
        self.timeout = timeout
        self.mqtt: MQTTManager = None
        self._task = None
        self._running = False

    def start(self, mqtt_client: MQTTManager):
        self.mqtt = mqtt_client
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        print(f"[ESP Manager] Servicio de latidos iniciado cada {self.ping_interval}s")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    def register_device(self, ip: str, name: str, initial_state: dict):
        self.devices[ip] = {
            "name": name,
            "status": "online",
            "last_seen": time.time(),
            "state": initial_state
        }
        print(f"[ESP Manager] Registrado {name} ({ip})")

    def unregister_device(self, ip: str):
        if ip in self.devices:
            del self.devices[ip]
            print(f"[ESP Manager] Dispositivo {ip} eliminado del monitoreo.")

    async def _heartbeat_loop(self):
        async with httpx.AsyncClient() as client:
            while self._running:
                for ip, device_info in list(self.devices.items()):
                    await self._ping_device(client, ip)
                await asyncio.sleep(self.ping_interval)

    async def _ping_device(self, client: httpx.AsyncClient, ip: str):
        device_info = self.devices[ip]
        try:
            # Endpoint ligero solo para comprobar vida
            response = await client.get(f"http://{ip}/ping", timeout=self.timeout)
            
            if response.status_code == 200:
                # Dispositivo vivo
                if device_info["status"] == "offline":
                    device_info["status"] = "online"
                    print(f"[ESP Manager] {device_info['name']} ({ip}) RECUPERADO.")
                    self._publish_device_status(ip, "reconnected")
                device_info["last_seen"] = time.time()
                
            else:
                self._handle_offline(ip, f"Error HTTP {response.status_code}")
                
        except (httpx.ConnectTimeout, httpx.ReadTimeout):
            self._handle_offline(ip, "Timeout")
        except httpx.ConnectError:
            self._handle_offline(ip, "Conexión rechazada")
        except Exception as e:
            self._handle_offline(ip, str(e))

    def _handle_offline(self, ip: str, reason: str):
        device_info = self.devices[ip]
        if device_info["status"] == "online":
            device_info["status"] = "offline"
            print(f"[ESP Manager] 🚨 ALERTA: {device_info['name']} ({ip}) DESCONECTADO. Razón: {reason}")
            self._publish_device_status(ip, "offline")

    def _publish_device_status(self, ip: str, event: str):
        if self.mqtt:
            payload = {
                "ip": ip,
                "event": event,
                "timestamp": time.time()
            }
            # Tópico específico de control de conexión
            self.mqtt.publish("finca/seguridad/patio/conexion", payload)
