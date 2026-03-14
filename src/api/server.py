from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os
import sys
import json

# Asegurar que el backend encuentre los módulos internos de la Tesis
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.agents.master.agent import WardenMasterCrew
from src.core.esp_manager import ESPManager
from src.core.mqtt_manager import MQTTManager
from src.core.device_db import init_db, add_device, get_device, list_devices, delete_device, update_state
from src.core.alexa_bridge import AlexaCloudBridge

# Gestión de clientes WebSockets conectados para broadcast
connected_mqtt_clients = set()
main_loop = None

app = FastAPI(title="Warden Command Center API")

# Habilitar CORS para evitar problemas de desarrollo cruzado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servimos la carpeta public (HTML/CSS/JS) para que la UI se monte en raíz "/"
public_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "public")
# Si el root es "/", entonces localhost:8000 servirá index.html automáticamente
app.mount("/ui", StaticFiles(directory=public_dir, html=True), name="public")


# Instancia única del Warden Master
warden = WardenMasterCrew()

# Instancias Globales para Background Services
esp_manager = ESPManager(ping_interval=10, timeout=3)
# Inicializar la base de datos de dispositivos al iniciar
init_db()

global_mqtt = MQTTManager(client_id="Warden_Global_Client")
alexa_bridge = AlexaCloudBridge(local_mqtt=global_mqtt)

def on_global_mqtt_message(topic, payload):
    """
    Escucha todos los mensajes MQTT globales y mantiene actualizada la base de datos
    local (device_db) con el estado en tiempo real de los ESP32.
    """
    from src.core.device_db import list_devices, update_state
    
    # Mapeo de topic estado a device type
    TOPIC_TO_DTYPE = {
        "finca/seguridad/patio/estado": "esp32_security",
        "finca/piscina/estado": "esp32_pool",
        "finca/cocina/estado": "esp32_kitchen",
        "finca/jardin/estado": "esp32_garden",
        "finca/sistema/modo": "system_mode"
    }
    
    try:
        if "estado" in topic:
            state_data = payload if isinstance(payload, dict) else json.loads(payload)
            matched_dtype = None
            for t, dtype in TOPIC_TO_DTYPE.items():
                if t == topic:
                    matched_dtype = dtype
                    break
            if matched_dtype:
                devices = list_devices()
                for dev in devices:
                    if dev["type"] == matched_dtype:
                        update_state(dev["ip"], state_data)
                        break
        elif topic == "finca/sistema/modo":
            mode = payload.get("mode", "Ninguno") if isinstance(payload, dict) else "Ninguno"
            # Ejecutamos la lógica de ráfaga de forma segura desde otro thread.
            # publish_sync=False porque el mensaje ya vino de MQTT.
            if main_loop:
                asyncio.run_coroutine_threadsafe(apply_system_mode_logic(mode, publish_sync=False), main_loop)

            
    except Exception as e:
        print(f"[Global MQTT] Error procesando mensaje: {e}")

async def apply_system_mode_logic(mode: str, publish_sync: bool = True):
    """
    Lógica central de ráfagas MQTT para los modos del sistema.
    publish_sync: Si es True, re-publica el modo al topic global para sincronizar otros nodos.
    """
    MODES_LOGIC = {
        "Manana": {
            "finca/cocina/comando": {"luces_cocina": "on", "luces_sala": "on", "luces_cabinet": "off"},
            "finca/piscina/comando": {"luces_pis": "off", "motor_pis": "on"},
            "finca/jardin/comando": {"luces_frente": "off"}
        },
        "Tarde": {
            "finca/cocina/comando": {"luces_cocina": "off", "luces_sala": "off", "luces_isla": "off"},
            "finca/jardin/comando": {"luces_frente": "off", "motor_fuente": "on"}
        },
        "Noche": {
            "finca/cocina/comando": {"luces_cocina": "off", "luces_sala": "on", "luces_isla": "on", "luces_cabinet": "on"},
            "finca/jardin/comando": {"luces_frente": "off", "luces_camino": "on", "luces_fuente": "on"},
            "finca/piscina/comando": {"luces_pis": "on"}
        },
        "Dormir": {
            "finca/cocina/comando": {"luces_cocina": "off", "luces_sala": "off", "luces_isla": "off", "luces_cabinet": "off", "sirena": "off"},
            "finca/jardin/comando": {"luces_frente": "off", "luces_camino": "off", "motor_fuente": "off"},
            "finca/piscina/comando": {"luces_pis": "off", "luces_jac": "off", "motor_pis": "off", "motor_jac": "off"},
            "finca/seguridad/patio/siren/comando": {"accion": "off"}
        },
        "Tarde Alegre": {
            "finca/piscina/comando": {"luces_pis": "on", "luces_jac": "on", "motor_jac": "on"},
            "finca/cocina/comando": {"luces_isla": "on"}
        },
        "Noche Romantica": {
            "finca/cocina/comando": {"luces_isla": "on", "luces_cabinet": "on", "luces_cocina": "off", "luces_sala": "off"},
            "finca/jardin/comando": {"luces_fuente": "on", "motor_fuente": "on"}
        },
        "Fiesta": {
            "finca/cocina/comando": {"luces_cocina": "on", "luces_sala": "on", "luces_isla": "on", "luces_cabinet": "on"},
            "finca/piscina/comando": {"luces_pis": "on", "luces_jac": "on", "motor_jac": "on"},
            "finca/jardin/comando": {"luces_frente": "on", "luces_izq": "on", "luces_der": "on", "motor_fuente": "on"}
        },
        "Seguridad Maxima": {
            "finca/cocina/comando": {"luces_cocina": "on", "luces_sala": "on", "sirena": "on"},
            "finca/jardin/comando": {"luces_frente": "on", "luces_atras": "on", "luces_camino": "on"},
            "finca/seguridad/patio/siren/comando": {"accion": "on"}
        },
        "Mantenimiento": {
            "finca/cocina/comando": {"luces_cocina": "on", "luces_cabinet": "on"},
            "finca/piscina/comando": {"motor_pis": "on", "motor_jac": "off"}
        },
        "Yoga": {
            "finca/cocina/comando": {"luces_sala": "on", "luces_cocina": "off"},
            "finca/jardin/comando": {"motor_fuente": "on"}
        },
        "Estudio": {
            "finca/cocina/comando": {"luces_sala": "on", "luces_isla": "on"},
            "finca/jardin/comando": {"luces_frente": "on"}
        },
        "Ninguno": {}
    }

    commands = MODES_LOGIC.get(mode, {})
    if global_mqtt.client.is_connected():
        for topic, payload in commands.items():
            global_mqtt.publish(topic, payload)
        
        if publish_sync:
            # Sincronizar el modo globalmente vía MQTT para que los ESP32 reaccionen
            global_mqtt.publish("finca/sistema/modo", {"mode": mode})
        
        # Broadcast a todos los dashboards conectados vía WebSocket
        broadcast_msg = json.dumps({"type": "system_mode", "mode": mode})
        for ws in connected_mqtt_clients.copy():
            try:
                asyncio.create_task(ws.send_text(broadcast_msg))
            except:
                connected_mqtt_clients.remove(ws)
        
        return True
    return False

def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    print(f"[Global MQTT] CONECTADO AL BROKER. RC: {rc}")
    client.subscribe("finca/#")
    print("[Global MQTT] Suscrito a finca/#")

def on_alexa_mode_change(mode):
    """Callback directo desde el AlexaBridge para evitar loopbacks de MQTT"""
    print(f"[Server] Cambio de modo detectado vía Alexa: {mode}")
    if main_loop:
        asyncio.run_coroutine_threadsafe(apply_system_mode_logic(mode, publish_sync=True), main_loop)

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    print("[Server] Iniciando servicios en segundo plano...")
    
    global_mqtt.client.on_connect = on_mqtt_connect
    global_mqtt.on_message_callback = on_global_mqtt_message
    
    # Vincular callback directo de modo
    alexa_bridge.on_mode_change = on_alexa_mode_change
    
    if global_mqtt.connect():
        # Suscribir a los canales de estado de todos los módulos
        global_mqtt.subscribe("finca/+/estado")
        global_mqtt.subscribe("finca/sistema/modo")
        global_mqtt.subscribe("finca/seguridad/patio/estado")
        esp_manager.start(global_mqtt)
        alexa_bridge.start()
    else:
        print("[Server] ERROR: No se pudo iniciar el cliente MQTT.")

@app.on_event("shutdown")
async def shutdown_event():
    print("[Server] Apagando servicios...")
    esp_manager.stop()
    alexa_bridge.stop()
    global_mqtt.disconnect()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Recibe un prompt del frontend web. Posee un atajo heurístico de NLP para 
    control directo y seguro de actuadores, y hace fallback a CrewAI/Llama3
    para preguntas complejas.
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    
    msg_lower = request.message.lower()
    
    # --- ATAJO HEURÍSTICO NLP PARA CONTROL DIRECTO DE HARDWARE ---
    # Si detecta una instrucción de control (encender/apagar), lo hace directo sin LLM.
    if ("encend" in msg_lower or "apag" in msg_lower or "prend" in msg_lower):
        from src.core.device_db import list_devices
        devices = list_devices()
        
        # Determinar acción
        accion = "on" if ("encend" in msg_lower or "prend" in msg_lower) else "off"
        
        # Mapa heurístico expansivo
        # Si un key tiene 'area_required': False, no necesita que se mencione el área explícitamente.
        synonyms = [
            {"area": "piscina", "dtype": "esp32_pool", "area_required": True, "acts": {
                "luces de la piscina": "luces_pis", "luz piscina": "luces_pis", "luz de piscina": "luces_pis",
                "motor de la piscina": "motor_pis", "bomba piscina": "motor_pis", "motor piscina": "motor_pis"
            }},
            {"area": "jacuzzi", "dtype": "esp32_pool", "area_required": False, "acts": {
                "luz jacuzzi": "luces_jac", "luces jacuzzi": "luces_jac", "luces del jacuzzi": "luces_jac",
                "motor jacuzzi": "motor_jac", "bomba jacuzzi": "motor_jac", "motor del jacuzzi": "motor_jac", "jacuzzi motor": "motor_jac"
            }},
            {"area": "cocina", "dtype": "esp32_kitchen", "area_required": True, "acts": {
                "luces de la cocina": "luces_cocina", "luz cocina": "luces_cocina", "luz de la cocina": "luces_cocina"
            }},
            {"area": "cocina_especificos", "dtype": "esp32_kitchen", "area_required": False, "acts": {
                "cabinet": "luces_cabinet", "gabinete": "luces_cabinet",
                "isla": "luces_isla", "luces de la isla": "luces_isla",
                "sala": "luces_sala", "luces de la sala": "luces_sala",
                "sirena": "sirena"
            }},
            {"area": "jardin", "dtype": "esp32_garden", "area_required": False, "acts": {
                "luces del jardin": "luces_frente", "luces jardin": "luces_frente", "luz jardin": "luces_frente",
                "izquierda": "luces_izq", "izq": "luces_izq",
                "derecha": "luces_der", "der": "luces_der",
                "frente": "luces_frente", "atras": "luces_atras",
                "camino": "luces_camino",
                "motor fuente": "motor_fuente", "fuente": "motor_fuente", "motor de la fuente": "motor_fuente",
                "luz fuente": "luces_fuente", "luces fuente": "luces_fuente"
            }}
        ]
        
        target_dtype = None
        target_actuator = None
        import re
        
        # 1. Buscar coincidencias exactas y específicas primero (sin importar área)
        for cat in synonyms:
            for term, act_key in cat["acts"].items():
                if re.search(r'\b' + re.escape(str(term)) + r'\b', msg_lower):
                    if not cat.get("area_required") or cat.get("area", "") in msg_lower:
                        target_dtype = cat["dtype"]
                        target_actuator = act_key
                        break
            if target_actuator: break
            
        # 2. Búsqueda genérica si solo detectó área y "luces"
        if not target_actuator and re.search(r'\bluces\b|\bluz\b', msg_lower):
            for cat in synonyms:
                if cat["area"] in msg_lower:
                    target_dtype = cat["dtype"]
                    if cat["area"] == "cocina": target_actuator = "luces_cocina"
                    if cat["area"] == "piscina": target_actuator = "luces_pis"
                    if cat["area"] == "jardin": target_actuator = "luces_frente"
                    break
                
        if target_dtype and target_actuator:
            # Buscar el dispositivo en línea que corresponda a este dtype
            target_ip = None
            for d in devices:
                if d["type"] == target_dtype:
                    target_ip = d["ip"]
                    break
                    
            if target_ip:
                print(f"[NLP Directo] Ejecutando: {target_actuator} -> {accion} en {target_ip}")
                # Publicar directo a MQTT usando el mapeo
                TOPIC_MAP = {
                    "esp32_security": "finca/seguridad/patio/siren/comando",
                    "esp32_pool":     "finca/piscina/comando",
                    "esp32_kitchen":  "finca/cocina/comando",
                    "esp32_garden":   "finca/jardin/comando",
                }
                if global_mqtt.client.is_connected():
                    global_mqtt.publish(TOPIC_MAP[target_dtype], {target_actuator: accion})
                    estado_str = "encendidas" if accion == "on" else "apagadas"
                    if target_actuator.startswith("motor"): estado_str = "encendido" if accion == "on" else "apagado"
                    return ChatResponse(reply=f"Acción directa ejecutada por Yarvis: {target_actuator.replace('_', ' ')} {estado_str}.")
                else:
                    return ChatResponse(reply="Yarvis: Mi conexión a la red MQTT local está caída.")
            else:
                return ChatResponse(reply=f"Yarvis: Entiendo la orden, pero no hay ningún módulo físico de '{target_dtype}' en línea ahora mismo.")
    
    # --- FALLBACK A LLM ---
    # Procesar con el Master Agent para conversaciones complejas
    try:
        print("[LLM Router] Derivando consulta compleja a Ollama/CrewAI...")
        respuesta = warden.chat_with_warden(request.message)
        return ChatResponse(reply=respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import subprocess

@app.post("/api/sentinel")
async def start_sentinel_endpoint():
    """
    Inicia el script de visión por computadora en un proceso separado para que abra la ventana.
    """
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "vision", "sentinel.py")
    try:
        # Lanzamos Sentinel en background para que no bloquee el backend FastAPI
        # La ventana de OpenCV se abrirá en el propio Windows (Edge Server)
        subprocess.Popen([sys.executable, script_path])
        return {"status": "Sentinel Vision Thread Activated! Window Opening..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate_motion")
async def simulate_motion_endpoint():
    """
    Recibe un request REST HTTP de la app móvil (Expo) y lo puentea a MQTT.
    Esto evita lidiar con polyfills de Buffer/WebSockets en React Native antiguo.
    """
    try:
        if global_mqtt.client.is_connected():
            global_mqtt.publish("finca/seguridad/patio/movimiento", {"motion": True})
            return {"status": "ok", "message": "Movimiento simulado enviado a MQTT."}
        else:
            raise HTTPException(status_code=503, detail="Broker MQTT local desconectado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SystemModeRequest(BaseModel):
    mode: str

@app.post("/api/system/mode")
async def set_system_mode_endpoint(request: SystemModeRequest):
    """
    Activa un modo de sistema predefinido (Mañana, Noche, Fiesta, etc.).
    Envía ráfagas sincronizadas de comandos MQTT a todos los módulos necesarios.
    """
    mode = request.mode
    print(f"[System Mode] Activando modo: {mode}")
    success = await apply_system_mode_logic(mode)
    
    if success:
        replies = {
            "Manana": "Buenos días, Comandante. Luces interiores activadas y bomba de piscina en ciclo de filtrado.",
            "Noche": "Modo Noche activado. Iluminación perimetral y de estancia encendidas.",
            "Dormir": "Protocolo de descanso activo. Luces interiores apagadas. Perímetro en monitoreo silencioso.",
            "Fiesta": "Modo Fiesta iniciado. Sistemas de iluminación y motores a máxima capacidad. ¡Disfrute!",
            "Seguridad Maxima": "⚠️ ALERTA: Seguridad Máxima activada. Sirenas y todas las luces exteriores encendidas.",
            "Tarde Alegre": "Configuración de tarde alegre lista. Jacuzzi encendido.",
            "Noche Romantica": "Ambiente tenue configurado. Fuente activa.",
            "Yoga": "Modo Zen activo. Iluminación suave para su sesión.",
            "Estudio": "Configuración para estudio y lectura lista. Luces de sala e isla al máximo.",
            "Ninguno": "Sistema en modo manual."
        }
        
        reply = replies.get(mode, f"Modo {mode} activado con éxito.")
        return {"status": "success", "reply": reply}
    else:
        raise HTTPException(status_code=503, detail="Broker MQTT desconectado.")

@app.websocket("/api/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    Inicia el script de reconocimiento de voz sin ventana visible y transmite 
    sus logs y transcripciones en tiempo real al frontend vía WebSockets.
    """
    await websocket.accept()
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "voice", "voice_agent.py")
    
    try:
        # Lanzamos Voice Agent de forma invisible y capturamos stdout
        # -u para modo unbuffered en Python (para que el print se envíe de inmediato)
        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", script_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            env=env
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
                
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                # Enviar línea cruda al panel lateral (Telemetry)
                await websocket.send_json({"type": "log", "text": text})
                
                # Inyectar al Chat Web si hay comandos o respuestas
                if "[USER] COMANDO STT:" in text:
                    cmd = text.split("[USER] COMANDO STT:")[1].strip().strip("'")
                    await websocket.send_json({"type": "user_msg", "text": cmd})
                
                elif "[YARVIS] RESPONDE:" in text:
                    resp = text.split("[YARVIS] RESPONDE:")[1].strip().strip("'")
                    await websocket.send_json({"type": "assistant_msg", "text": resp})
                    
        await process.wait()
    except WebSocketDisconnect:
        print("[Server] Dashboard desconectado del Voice Agent. Cerrando micrófono...")
        if process.returncode is None:
            process.terminate()
    except Exception as e:
        print(f"[Server] Error en WebSocket Voice: {e}")
        if 'process' in locals() and process.returncode is None:
            process.terminate()

@app.websocket("/api/ws/mqtt")
async def mqtt_websocket(websocket: WebSocket):
    """
    Se conecta al bus MQTT local y retransmite todos los eventos de la finca
    directamente al terminal de telemetría del Dashboard.
    """
    await websocket.accept()
    connected_mqtt_clients.add(websocket) # Add to the set of active clients
    from src.core.mqtt_manager import MQTTManager
    
    # Capturar el loop de asyncio en el contexto correcto (Python 3.10+ compatible)
    loop = asyncio.get_event_loop()
    
    ui_mqtt = MQTTManager(client_id="Dashboard_Bridger")
    
    def on_broadcast(topic, payload):
        msg = {"topic": topic, "payload": payload}
        # Programar el envío en el loop de asyncio desde el thread de Paho
        asyncio.run_coroutine_threadsafe(websocket.send_json(msg), loop)

    ui_mqtt.on_message_callback = on_broadcast
    
    try:
        if ui_mqtt.connect():
            ui_mqtt.subscribe("finca/#")
            while True:
                await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("[Server] Dashboard cerrado. Desconectando bridge MQTT.")
        ui_mqtt.disconnect()
    except Exception as e:
        print(f"[Server] Error en Bridge MQTT: {e}")
        ui_mqtt.disconnect()

@app.post("/api/esp/add")
async def add_esp_device(data: dict):
    """
    Intenta vincular un nuevo dispositivo ESP por su IP.
    """
    ip = data.get("ip")
    if not ip:
        return {"status": "error", "message": "IP no proporcionada"}
    
    # Usar nombre y tipo enviado desde la UI
    device_name = data.get("name", "ESP32 Dispositivo")
    device_type = data.get("dtype", "esp32_security")
    
    import httpx
    try:
        # Timeout reducido para respuesta más rápida en UI (Fail-fast)
        async with httpx.AsyncClient() as client:
            print(f"[Server] Intentando conectar con ESP32 en http://{ip}/state")
            response = await client.get(f"http://{ip}/state", timeout=3.0)
            
            if response.status_code == 200:
                try:
                    esp_state = response.json()
                except Exception as json_e:
                    print(f"[Server] Error parseando JSON del ESP32: {json_e}")
                    return {"status": "error", "message": "Respuesta inválida del dispositivo"}

                # Notificar a MQTT que un nuevo dispositivo está siendo monitoreado
                if global_mqtt.client.is_connected():
                    global_mqtt.publish("finca/seguridad/patio/config", {"ip": ip, "status": "linked", "initial_state": esp_state})
                
                # Guardar en DB y registrar en manager
                saved = add_device(ip, device_name, dtype=device_type, state=esp_state)
                esp_manager.register_device(ip, device_name, esp_state)
                
                print(f"[Server] {device_name} ({device_type}) en {ip} vinculado con éxito.")
                return {"status": "success", "device": device_name, "dtype": device_type, "state": esp_state}
            else:
                print(f"[Server] ESP32 respondió con error {response.status_code}")
                return {"status": "error", "message": f"Dispositivo respondió con código {response.status_code}"}
    except httpx.ConnectTimeout:
        return {"status": "error", "message": f"Tiempo de espera agotado al conectar con {ip}"}
    except httpx.ConnectError:
         return {"status": "error", "message": f"Conexión rechazada por {ip}. Verifica que esté encendido."}
    except Exception as e:
        print(f"[Server] Error inesperado conectando a ESP32: {e}")
        return {"status": "error", "message": f"Error interno: {str(e)}"}

@app.post("/api/esp/siren")
async def toggle_siren(data: dict):
    """
    Envía el comando de sirena directamente al MQTT sin pasar por el LLM.
    Mucho más rápido para control de hardware en tiempo real.
    """
    accion = data.get("accion", "off")
    if global_mqtt.client.is_connected():
        global_mqtt.publish("finca/seguridad/patio/siren/comando", {"accion": accion})
        return {"status": "ok", "accion": accion}
    else:
        return {"status": "error", "message": "MQTT no conectado"}

@app.get("/api/esp/state")
async def get_esp_state(ip: str):
    """
    Obtiene el estado actual del ESP32 directamente por HTTP.
    Usado como fallback de polling por el Dashboard.
    """
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{ip}/state", timeout=2.0)
            return resp.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/devices")
async def get_devices():
    """Lista todos los dispositivos guardados en la DB."""
    return list_devices()

@app.delete("/api/devices/{ip:path}")
async def remove_device(ip: str):
    """Elimina un dispositivo de la DB."""
    delete_device(ip)
    esp_manager.unregister_device(ip)
    return {"status": "ok", "deleted": ip}

class ControlCmd(BaseModel):
    ip: str
    dtype: str         # "esp32_security" | "esp32_pool"
    command: dict      # {actuador: valor, ...}

@app.post("/api/esp/control")
async def control_device(cmd: ControlCmd):
    """
    Envía un comando MQTT al actuador del dispositivo indicado.
    El topic destino depende del tipo de dispositivo.
    """
    TOPIC_MAP = {
        "esp32_security": "finca/seguridad/patio/siren/comando",
        "esp32_pool":     "finca/piscina/comando",
        "esp32_kitchen":  "finca/cocina/comando",
        "esp32_garden":   "finca/jardin/comando",
    }
    topic = TOPIC_MAP.get(cmd.dtype)
    if not topic:
        raise HTTPException(status_code=400, detail=f"Tipo de dispositivo desconocido: {cmd.dtype}")

    if global_mqtt.client.is_connected():
        global_mqtt.publish(topic, cmd.command)
        # Actualizar estado en DB
        dev = get_device(cmd.ip) or {}
        state = dev.get("state") or {}
        if isinstance(state, dict):
            state.update(cmd.command)
            update_state(cmd.ip, state)
        return {"status": "ok", "topic": topic, "command": cmd.command}
    else:
        return {"status": "error", "message": "MQTT broker no conectado"}



@app.get("/api/esp/arduino/pool")
async def get_pool_arduino_code(ip: str = "192.168.1.132", broker_ip: str = "192.168.1.138"):
    """
    Genera el código C++ para el ESP32 de control de Piscina.
    Sensores: PIR, Nivel de agua.
    Actuadores: Luces piscina, Luces jacuzzi, Motor jacuzzi, Motor piscina.
    """
    code = f"""// === YARVIS POOL CONTROLLER ESP32 ===
// Generado por Yarvis Edge Command Center
//
// SENSORES:
//   PIN 14 = PIR Movimiento
//   PIN 35 = Nivel de Agua (HIGH = nivel bajo = necesita recarga)
//
// ACTUADORES (RELÉS - activo en LOW para relé normalmente abierto):
//   PIN 26 = Luces Fondo Piscina
//   PIN 27 = Luces Jacuzzi
//   PIN 32 = Motor Jacuzzi
//   PIN 33 = Motor Piscina
//
// TECLAS SERIAL MONITOR (testing sin hardware):
//   1 = Sensor Movimiento ON/OFF
//   2 = Nivel Agua NORMAL/BAJO
//   3 = Luces Piscina ON/OFF
//   4 = Luces Jacuzzi ON/OFF
//   5 = Motor Jacuzzi ON/OFF
//   6 = Motor Piscina ON/OFF
//   0 = APAGAR TODO (emergencia)

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid        = "TU_WIFI";
const char* password    = "TU_PASSWORD";
const char* mqtt_server = "{broker_ip}";

// ---- Pines ----
const int PIR_PIN        = 14;
const int WATER_PIN      = 35; // HIGH = nivel bajo
const int PIN_LUCES_PIS  = 26;
const int PIN_LUCES_JAC  = 27;
const int PIN_MOTOR_JAC  = 32;
const int PIN_MOTOR_PIS  = 33;

// ---- Topics MQTT ----
const char* TOPIC_ESTADO   = "finca/piscina/estado";
const char* TOPIC_COMANDO  = "finca/piscina/comando";

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// ---- States ----
bool s_motion      = false;
bool s_water_low   = false;
bool s_luces_pis   = false;
bool s_luces_jac   = false;
bool s_motor_jac   = false;
bool s_motor_pis   = false;

// Relay helper (LOW = ON para la mayoría de módulos de relé)
void setRelay(int pin, bool on) {{
  digitalWrite(pin, on ? LOW : HIGH);
}}

void publishState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]     = s_motion     ? "active" : "standby";
  doc["agua"]       = s_water_low  ? "nivel_bajo" : "normal";
  doc["luces_pis"]  = s_luces_pis  ? "on" : "off";
  doc["luces_jac"]  = s_luces_jac  ? "on" : "off";
  doc["motor_jac"]  = s_motor_jac  ? "on" : "off";
  doc["motor_pis"]  = s_motor_pis  ? "on" : "off";
  char buf[512];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ESTADO, buf);
  Serial.print("[MQTT] -> "); Serial.println(buf);
}}

void applyActuators() {{
  setRelay(PIN_LUCES_PIS, s_luces_pis);
  setRelay(PIN_LUCES_JAC, s_luces_jac);
  setRelay(PIN_MOTOR_JAC, s_motor_jac);
  setRelay(PIN_MOTOR_PIS, s_motor_pis);
}}

void emergencyOff() {{
  s_luces_pis = s_luces_jac = s_motor_jac = s_motor_pis = false;
  applyActuators();
  Serial.println("[!] APAGADO DE EMERGENCIA");
  publishState();
}}

void callback(char* topic, byte* payload, unsigned int length) {{
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("[MQTT CMD] "); Serial.println(msg);

  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, msg) != DeserializationError::Ok) return;

  if (doc.containsKey("luces_pis"))  {{ s_luces_pis = (String(doc["luces_pis"].as<const char*>()) == "on"); }}
  if (doc.containsKey("luces_jac"))  {{ s_luces_jac = (String(doc["luces_jac"].as<const char*>()) == "on"); }}
  if (doc.containsKey("motor_jac"))  {{ s_motor_jac = (String(doc["motor_jac"].as<const char*>()) == "on"); }}
  if (doc.containsKey("motor_pis"))  {{ s_motor_pis = (String(doc["motor_pis"].as<const char*>()) == "on"); }}
  if (doc.containsKey("apagar_todo") && doc["apagar_todo"].as<bool>()) {{ emergencyOff(); return; }}

  applyActuators();
  publishState();
}}

void reconnect() {{
  while (!mqtt.connected()) {{
    Serial.print("Conectando MQTT...");
    if (mqtt.connect("ESP32_Pool_Client")) {{
      Serial.println("OK");
      mqtt.subscribe(TOPIC_COMANDO);
      publishState();
    }} else {{
      Serial.print("Error rc="); Serial.println(mqtt.state());
      delay(3000);
    }}
  }}
}}

void handleState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]    = s_motion    ? "active" : "standby";
  doc["agua"]      = s_water_low ? "nivel_bajo" : "normal";
  doc["luces_pis"] = s_luces_pis ? "on" : "off";
  doc["luces_jac"] = s_luces_jac ? "on" : "off";
  doc["motor_jac"] = s_motor_jac ? "on" : "off";
  doc["motor_pis"] = s_motor_pis ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}}

void handlePing() {{ server.send(200, "text/plain", "pong"); }}

void handleSerialInput(char key) {{
  switch (key) {{
    case '1': s_motion    = !s_motion;
              Serial.println(s_motion    ? "[1] Movimiento: ACTIVO"   : "[1] Movimiento: INACTIVO"); break;
    case '2': s_water_low = !s_water_low;
              Serial.println(s_water_low ? "[2] Agua: NIVEL BAJO"     : "[2] Agua: NORMAL"); break;
    case '3': s_luces_pis = !s_luces_pis;
              Serial.println(s_luces_pis ? "[3] Luces Piscina: ON"    : "[3] Luces Piscina: OFF"); break;
    case '4': s_luces_jac = !s_luces_jac;
              Serial.println(s_luces_jac ? "[4] Luces Jacuzzi: ON"    : "[4] Luces Jacuzzi: OFF"); break;
    case '5': s_motor_jac = !s_motor_jac;
              Serial.println(s_motor_jac ? "[5] Motor Jacuzzi: ON"    : "[5] Motor Jacuzzi: OFF"); break;
    case '6': s_motor_pis = !s_motor_pis;
              Serial.println(s_motor_pis ? "[6] Motor Piscina: ON"    : "[6] Motor Piscina: OFF"); break;
    case '0': emergencyOff(); return;
    default:
      Serial.println("Teclas: 1=Mov 2=Agua 3=LucesPis 4=LucesJac 5=MotorJac 6=MotorPis 0=APAGAR_TODO");
      return;
  }}
  applyActuators();
  publishState();
}}

void setup_wifi() {{
  Serial.print("WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {{ delay(500); Serial.print("."); }}
  Serial.print(" IP: "); Serial.println(WiFi.localIP());
}}

void setup() {{
  Serial.begin(115200);
  // Pines sensores
  pinMode(PIR_PIN, INPUT);
  pinMode(WATER_PIN, INPUT);
  // Pines actuadores — relés apagados al iniciar
  pinMode(PIN_LUCES_PIS, OUTPUT); digitalWrite(PIN_LUCES_PIS, HIGH);
  pinMode(PIN_LUCES_JAC, OUTPUT); digitalWrite(PIN_LUCES_JAC, HIGH);
  pinMode(PIN_MOTOR_JAC, OUTPUT); digitalWrite(PIN_MOTOR_JAC, HIGH);
  pinMode(PIN_MOTOR_PIS, OUTPUT); digitalWrite(PIN_MOTOR_PIS, HIGH);

  setup_wifi();
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);
  server.on("/state", handleState);
  server.on("/ping", handlePing);
  server.begin();

  Serial.println("\\n=== YARVIS POOL CONTROLLER LISTO ===");
  Serial.println("Teclas: 1=Mov 2=Agua 3=LucesPis 4=LucesJac 5=MotorJac 6=MotorPis 0=APAGAR");
}}

bool last_pir = false;
bool last_water = false;

void loop() {{
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Leer sensores físicos y publicar solo si cambian
  bool pir   = digitalRead(PIR_PIN) == HIGH;
  bool water = digitalRead(WATER_PIN) == HIGH; // HIGH = nivel bajo
  if (pir != last_pir || water != last_water) {{
    s_motion    = pir;
    s_water_low = water;
    last_pir    = pir;
    last_water  = water;
    publishState();
    if (s_water_low) Serial.println("[!] ALERTA: Nivel de agua bajo");
  }}

  // Tecla del Serial Monitor para testing
  if (Serial.available() > 0) {{
    handleSerialInput(Serial.read());
  }}
  delay(50);
}}
"""
    return {"arduino_code": code}

@app.get("/api/esp/arduino/kitchen")
async def get_kitchen_arduino_code(ip: str = "192.168.1.133", broker_ip: str = "192.168.1.138"):
    """
    Genera el código C++ para el ESP32 de control de Cocina.
    Sensores: PIR, MQ-7 Monóxido de Carbono (analógico), MQ-2 Humo (digital).
    Actuadores (relés): Luces Cabinet, Luces Cocina, Sirena, Luces Isla, Luces Sala.
    """
    code = f"""// === YARVIS KITCHEN CONTROLLER ESP32 ===
// Generado por Yarvis Edge Command Center
//
// SENSORES:
//   PIN 14  = PIR Movimiento
//   PIN 34  = MQ-7 Monóxido de Carbono (analógico, >1800 = alerta)
//   PIN 35  = MQ-2 Humo (digital, LOW = humo detectado)
//
// ACTUADORES (RELÉS - activo en LOW):
//   PIN 26  = Luces Cabinet
//   PIN 27  = Luces Cocina
//   PIN 32  = Sirena Cocina
//   PIN 33  = Luces Isla
//   PIN 25  = Luces Sala
//
// TECLAS SERIAL MONITOR (testing sin hardware):
//   1 = Movimiento ON/OFF
//   2 = Monóxido NORMAL/ALERTA
//   3 = Humo NORMAL/DETECTADO
//   4 = Luces Cabinet ON/OFF
//   5 = Luces Cocina ON/OFF
//   6 = Sirena ON/OFF
//   7 = Luces Isla ON/OFF
//   8 = Luces Sala ON/OFF
//   0 = APAGAR TODO (emergencia)

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid        = "TU_WIFI";
const char* password    = "TU_PASSWORD";
const char* mqtt_server = "{broker_ip}";

// ---- Pines Sensores ----
const int PIR_PIN    = 14;
const int CO_PIN     = 34;   // Analógico
const int SMOKE_PIN  = 35;   // Digital: LOW = humo

// ---- Pines Actuadores (Relés) ----
const int PIN_LUCES_CAB  = 26;
const int PIN_LUCES_COC  = 27;
const int PIN_SIRENA     = 32;
const int PIN_LUCES_ISL  = 33;
const int PIN_LUCES_SAL  = 25;

// ---- Umbrales ----
const int CO_THRESHOLD = 1800;  // Valor ADC > umbral = peligro

// ---- Topics MQTT ----
const char* TOPIC_ESTADO  = "finca/cocina/estado";
const char* TOPIC_COMANDO = "finca/cocina/comando";

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// ---- Estados ----
bool s_motion       = false;
bool s_co_alert     = false;
bool s_humo         = false;
bool s_luces_cab    = false;
bool s_luces_coc    = false;
bool s_sirena       = false;
bool s_luces_isl    = false;
bool s_luces_sal    = false;

void setRelay(int pin, bool on) {{
  digitalWrite(pin, on ? LOW : HIGH);
}}

void applyActuators() {{
  setRelay(PIN_LUCES_CAB,  s_luces_cab);
  setRelay(PIN_LUCES_COC,  s_luces_coc);
  setRelay(PIN_SIRENA,     s_sirena);
  setRelay(PIN_LUCES_ISL,  s_luces_isl);
  setRelay(PIN_LUCES_SAL,  s_luces_sal);
}}

void publishState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]       = s_motion    ? "active"    : "standby";
  doc["co"]           = s_co_alert  ? "alerta"    : "normal";
  doc["humo"]         = s_humo      ? "detectado" : "normal";
  doc["luces_cabinet"]= s_luces_cab ? "on" : "off";
  doc["luces_cocina"] = s_luces_coc ? "on" : "off";
  doc["sirena"]       = s_sirena    ? "on" : "off";
  doc["luces_isla"]   = s_luces_isl ? "on" : "off";
  doc["luces_sala"]   = s_luces_sal ? "on" : "off";
  char buf[512];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ESTADO, buf);
  Serial.print("[MQTT] -> "); Serial.println(buf);
}}

void emergencyOff() {{
  s_luces_cab = s_luces_coc = s_sirena = s_luces_isl = s_luces_sal = false;
  applyActuators();
  Serial.println("[!] APAGADO DE EMERGENCIA");
  publishState();
}}

void callback(char* topic, byte* payload, unsigned int length) {{
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("[MQTT CMD] "); Serial.println(msg);

  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, msg) != DeserializationError::Ok) return;

  if (doc.containsKey("luces_cabinet")) s_luces_cab = (String(doc["luces_cabinet"].as<const char*>()) == "on");
  if (doc.containsKey("luces_cocina"))  s_luces_coc = (String(doc["luces_cocina"].as<const char*>())  == "on");
  if (doc.containsKey("sirena"))        s_sirena    = (String(doc["sirena"].as<const char*>())         == "on");
  if (doc.containsKey("luces_isla"))    s_luces_isl = (String(doc["luces_isla"].as<const char*>())    == "on");
  if (doc.containsKey("luces_sala"))    s_luces_sal = (String(doc["luces_sala"].as<const char*>())    == "on");
  if (doc.containsKey("apagar_todo") && doc["apagar_todo"].as<bool>()) {{ emergencyOff(); return; }}

  applyActuators();
  publishState();
}}

void reconnect() {{
  while (!mqtt.connected()) {{
    Serial.print("Conectando MQTT...");
    if (mqtt.connect("ESP32_Kitchen_Client")) {{
      Serial.println("OK");
      mqtt.subscribe(TOPIC_COMANDO);
      publishState();
    }} else {{
      Serial.print("Error rc="); Serial.println(mqtt.state());
      delay(3000);
    }}
  }}
}}

void handleState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]        = s_motion    ? "active"    : "standby";
  doc["co"]            = s_co_alert  ? "alerta"    : "normal";
  doc["humo"]          = s_humo      ? "detectado" : "normal";
  doc["luces_cabinet"] = s_luces_cab ? "on" : "off";
  doc["luces_cocina"]  = s_luces_coc ? "on" : "off";
  doc["sirena"]        = s_sirena    ? "on" : "off";
  doc["luces_isla"]    = s_luces_isl ? "on" : "off";
  doc["luces_sala"]    = s_luces_sal ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}}

void handlePing() {{ server.send(200, "text/plain", "pong"); }}

void handleSerialInput(char key) {{
  switch (key) {{
    case '1': s_motion    = !s_motion;
              Serial.println(s_motion    ? "[1] Movimiento: ACTIVO"       : "[1] Movimiento: INACTIVO"); break;
    case '2': s_co_alert  = !s_co_alert;
              Serial.println(s_co_alert  ? "[2] CO: ALERTA"               : "[2] CO: NORMAL"); break;
    case '3': s_humo      = !s_humo;
              Serial.println(s_humo      ? "[3] Humo: DETECTADO"          : "[3] Humo: NORMAL"); break;
    case '4': s_luces_cab = !s_luces_cab;
              Serial.println(s_luces_cab ? "[4] Luces Cabinet: ON"        : "[4] Luces Cabinet: OFF"); break;
    case '5': s_luces_coc = !s_luces_coc;
              Serial.println(s_luces_coc ? "[5] Luces Cocina: ON"         : "[5] Luces Cocina: OFF"); break;
    case '6': s_sirena    = !s_sirena;
              Serial.println(s_sirena    ? "[6] Sirena: ON"               : "[6] Sirena: OFF"); break;
    case '7': s_luces_isl = !s_luces_isl;
              Serial.println(s_luces_isl ? "[7] Luces Isla: ON"           : "[7] Luces Isla: OFF"); break;
    case '8': s_luces_sal = !s_luces_sal;
              Serial.println(s_luces_sal ? "[8] Luces Sala: ON"           : "[8] Luces Sala: OFF"); break;
    case '0': emergencyOff(); return;
    default:
      Serial.println("Teclas: 1=Mov 2=CO 3=Humo 4=Cabinet 5=Cocina 6=Sirena 7=Isla 8=Sala 0=APAGAR");
      return;
  }}
  applyActuators();
  publishState();
}}

bool last_pir   = false;
bool last_co    = false;
bool last_humo  = false;

void setup() {{
  Serial.begin(115200);

  // Sensores
  pinMode(PIR_PIN,   INPUT);
  pinMode(SMOKE_PIN, INPUT_PULLUP); // LOW = humo

  // Actuadores — relés APAGADOS al iniciar
  pinMode(PIN_LUCES_CAB, OUTPUT); digitalWrite(PIN_LUCES_CAB, HIGH);
  pinMode(PIN_LUCES_COC, OUTPUT); digitalWrite(PIN_LUCES_COC, HIGH);
  pinMode(PIN_SIRENA,    OUTPUT); digitalWrite(PIN_SIRENA,    HIGH);
  pinMode(PIN_LUCES_ISL, OUTPUT); digitalWrite(PIN_LUCES_ISL, HIGH);
  pinMode(PIN_LUCES_SAL, OUTPUT); digitalWrite(PIN_LUCES_SAL, HIGH);

  // WiFi
  Serial.print("WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {{ delay(500); Serial.print("."); }}
  Serial.print(" IP: "); Serial.println(WiFi.localIP());

  // MQTT
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);

  // HTTP
  server.on("/state", handleState);
  server.on("/ping",  handlePing);
  server.begin();

  Serial.println("\\n=== YARVIS KITCHEN CONTROLLER LISTO ===");
  Serial.println("Teclas: 1=Mov 2=CO 3=Humo 4=Cabinet 5=Cocina 6=Sirena 7=Isla 8=Sala 0=APAGAR");
}}

void loop() {{
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Sensores físicos
  bool pir  = digitalRead(PIR_PIN) == HIGH;
  int  co   = analogRead(CO_PIN);
  bool humo = digitalRead(SMOKE_PIN) == LOW; // LOW = humo detectado

  bool co_alert = (co > CO_THRESHOLD);

  if (pir != last_pir || co_alert != last_co || humo != last_humo) {{
    s_motion   = pir;
    s_co_alert = co_alert;
    s_humo     = humo;
    last_pir   = pir;
    last_co    = co_alert;
    last_humo  = humo;
    publishState();
    if (co_alert) Serial.printf("[!] ALERTA CO: ADC=%d\\n", co);
    if (humo)     Serial.println("[!] ALERTA HUMO DETECTADO");
  }}

  // Testing serial
  if (Serial.available() > 0) {{
    handleSerialInput(Serial.read());
  }}
  delay(50);
}}
"""
    return {"arduino_code": code}

@app.get("/api/esp/arduino/garden")
async def get_garden_arduino_code(ip: str = "192.168.1.134", broker_ip: str = "192.168.1.138"):
    """
    Genera el código C++ para el ESP32 de control de Luces Jardín.
    Sensores: PIR Movimiento.
    Actuadores (relés): Luces Izq, Luces Der, Luces Frente, Luces Atrás, Motor Fuente, Luces Fuente, Luces Camino.
    """
    code = f"""// === YARVIS GARDEN CONTROLLER ESP32 ===
// Generado por Yarvis Edge Command Center
//
// SENSORES:
//   PIN 14  = PIR Movimiento
//
// ACTUADORES (RELÉS - activo en LOW):
//   PIN 26  = Luces Izq
//   PIN 27  = Luces Der
//   PIN 32  = Luces Frente
//   PIN 33  = Luces Atrás
//   PIN 25  = Motor Fuente
//   PIN 12  = Luces Fuente
//   PIN 13  = Luces Camino
//
// TECLAS SERIAL MONITOR (testing sin hardware):
//   1 = Movimiento ON/OFF
//   2 = Luces Izq ON/OFF
//   3 = Luces Der ON/OFF
//   4 = Luces Frente ON/OFF
//   5 = Luces Atrás ON/OFF
//   6 = Motor Fuente ON/OFF
//   7 = Luces Fuente ON/OFF
//   8 = Luces Camino ON/OFF
//   0 = APAGAR TODO

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid        = "TU_WIFI";
const char* password    = "TU_PASSWORD";
const char* mqtt_server = "{broker_ip}";

// ---- Pines Sensores ----
const int PIR_PIN = 14;

// ---- Pines Actuadores (Relés) ----
const int PIN_LUCES_IZQ    = 26;
const int PIN_LUCES_DER    = 27;
const int PIN_LUCES_FRENTE = 32;
const int PIN_LUCES_ATRAS  = 33;
const int PIN_MOTOR_FUENTE = 25;
const int PIN_LUCES_FUENTE = 12;
const int PIN_LUCES_CAMINO = 13;

// ---- Topics MQTT ----
const char* TOPIC_ESTADO  = "finca/jardin/estado";
const char* TOPIC_COMANDO = "finca/jardin/comando";

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// ---- Estados ----
bool s_motion       = false;
bool s_luces_izq    = false;
bool s_luces_der    = false;
bool s_luces_frente = false;
bool s_luces_atras  = false;
bool s_motor_fuente = false;
bool s_luces_fuente = false;
bool s_luces_camino = false;

void setRelay(int pin, bool on) {{
  digitalWrite(pin, on ? LOW : HIGH);
}}

void applyActuators() {{
  setRelay(PIN_LUCES_IZQ,    s_luces_izq);
  setRelay(PIN_LUCES_DER,    s_luces_der);
  setRelay(PIN_LUCES_FRENTE, s_luces_frente);
  setRelay(PIN_LUCES_ATRAS,  s_luces_atras);
  setRelay(PIN_MOTOR_FUENTE, s_motor_fuente);
  setRelay(PIN_LUCES_FUENTE, s_luces_fuente);
  setRelay(PIN_LUCES_CAMINO, s_luces_camino);
}}

void publishState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]       = s_motion       ? "active" : "standby";
  doc["luces_izq"]    = s_luces_izq    ? "on" : "off";
  doc["luces_der"]    = s_luces_der    ? "on" : "off";
  doc["luces_frente"] = s_luces_frente ? "on" : "off";
  doc["luces_atras"]  = s_luces_atras  ? "on" : "off";
  doc["motor_fuente"] = s_motor_fuente ? "on" : "off";
  doc["luces_fuente"] = s_luces_fuente ? "on" : "off";
  doc["luces_camino"] = s_luces_camino ? "on" : "off";
  char buf[512];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ESTADO, buf);
  Serial.print("[MQTT] -> "); Serial.println(buf);
}}

void emergencyOff() {{
  s_luces_izq = s_luces_der = s_luces_frente = s_luces_atras = false;
  s_motor_fuente = s_luces_fuente = s_luces_camino = false;
  applyActuators();
  Serial.println("[!] APAGADO GENERAL");
  publishState();
}}

void callback(char* topic, byte* payload, unsigned int length) {{
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("[MQTT CMD] "); Serial.println(msg);

  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, msg) != DeserializationError::Ok) return;

  if (doc.containsKey("luces_izq"))    s_luces_izq    = (String(doc["luces_izq"].as<const char*>())    == "on");
  if (doc.containsKey("luces_der"))    s_luces_der    = (String(doc["luces_der"].as<const char*>())    == "on");
  if (doc.containsKey("luces_frente")) s_luces_frente = (String(doc["luces_frente"].as<const char*>()) == "on");
  if (doc.containsKey("luces_atras"))  s_luces_atras  = (String(doc["luces_atras"].as<const char*>())  == "on");
  if (doc.containsKey("motor_fuente")) s_motor_fuente = (String(doc["motor_fuente"].as<const char*>()) == "on");
  if (doc.containsKey("luces_fuente")) s_luces_fuente = (String(doc["luces_fuente"].as<const char*>()) == "on");
  if (doc.containsKey("luces_camino")) s_luces_camino = (String(doc["luces_camino"].as<const char*>()) == "on");
  if (doc.containsKey("apagar_todo") && doc["apagar_todo"].as<bool>()) {{ emergencyOff(); return; }}

  applyActuators();
  publishState();
}}

void reconnect() {{
  while (!mqtt.connected()) {{
    Serial.print("Conectando MQTT...");
    if (mqtt.connect("ESP32_Garden_Client")) {{
      Serial.println("OK");
      mqtt.subscribe(TOPIC_COMANDO);
      publishState();
    }} else {{
      Serial.print("Error rc="); Serial.println(mqtt.state());
      delay(3000);
    }}
  }}
}}

void handleState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]       = s_motion       ? "active" : "standby";
  doc["luces_izq"]    = s_luces_izq    ? "on" : "off";
  doc["luces_der"]    = s_luces_der    ? "on" : "off";
  doc["luces_frente"] = s_luces_frente ? "on" : "off";
  doc["luces_atras"]  = s_luces_atras  ? "on" : "off";
  doc["motor_fuente"] = s_motor_fuente ? "on" : "off";
  doc["luces_fuente"] = s_luces_fuente ? "on" : "off";
  doc["luces_camino"] = s_luces_camino ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}}

void handlePing() {{ server.send(200, "text/plain", "pong"); }}

void handleSerialInput(char key) {{
  switch (key) {{
    case '1': s_motion       = !s_motion;
              Serial.println(s_motion       ? "[1] Movimiento: ACTIVO" : "[1] Movimiento: INACTIVO"); break;
    case '2': s_luces_izq    = !s_luces_izq;
              Serial.println(s_luces_izq    ? "[2] Luces Izq: ON"      : "[2] Luces Izq: OFF"); break;
    case '3': s_luces_der    = !s_luces_der;
              Serial.println(s_luces_der    ? "[3] Luces Der: ON"      : "[3] Luces Der: OFF"); break;
    case '4': s_luces_frente = !s_luces_frente;
              Serial.println(s_luces_frente ? "[4] Luces Frente: ON"   : "[4] Luces Frente: OFF"); break;
    case '5': s_luces_atras  = !s_luces_atras;
              Serial.println(s_luces_atras  ? "[5] Luces Atrás: ON"    : "[5] Luces Atrás: OFF"); break;
    case '6': s_motor_fuente = !s_motor_fuente;
              Serial.println(s_motor_fuente ? "[6] Motor Fuente: ON"   : "[6] Motor Fuente: OFF"); break;
    case '7': s_luces_fuente = !s_luces_fuente;
              Serial.println(s_luces_fuente ? "[7] Luces Fuente: ON"   : "[7] Luces Fuente: OFF"); break;
    case '8': s_luces_camino = !s_luces_camino;
              Serial.println(s_luces_camino ? "[8] Luces Camino: ON"   : "[8] Luces Camino: OFF"); break;
    case '0': emergencyOff(); return;
    default:
      Serial.println("Teclas: 1=Mov 2=Izq 3=Der 4=Frente 5=Atrás 6=Motor 7=L.Fuente 8=Camino 0=APAGAR");
      return;
  }}
  applyActuators();
  publishState();
}}

bool last_pir = false;

void setup() {{
  Serial.begin(115200);

  // Sensores
  pinMode(PIR_PIN, INPUT);

  // Actuadores — relés APAGADOS al iniciar (HIGH si son activos en LOW)
  pinMode(PIN_LUCES_IZQ,    OUTPUT); digitalWrite(PIN_LUCES_IZQ,    HIGH);
  pinMode(PIN_LUCES_DER,    OUTPUT); digitalWrite(PIN_LUCES_DER,    HIGH);
  pinMode(PIN_LUCES_FRENTE, OUTPUT); digitalWrite(PIN_LUCES_FRENTE, HIGH);
  pinMode(PIN_LUCES_ATRAS,  OUTPUT); digitalWrite(PIN_LUCES_ATRAS,  HIGH);
  pinMode(PIN_MOTOR_FUENTE, OUTPUT); digitalWrite(PIN_MOTOR_FUENTE, HIGH);
  pinMode(PIN_LUCES_FUENTE, OUTPUT); digitalWrite(PIN_LUCES_FUENTE, HIGH);
  pinMode(PIN_LUCES_CAMINO, OUTPUT); digitalWrite(PIN_LUCES_CAMINO, HIGH);

  // WiFi
  Serial.print("WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {{ delay(500); Serial.print("."); }}
  Serial.print(" IP: "); Serial.println(WiFi.localIP());

  // MQTT
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);

  // HTTP
  server.on("/state", handleState);
  server.on("/ping",  handlePing);
  server.begin();

  Serial.println("\\n=== YARVIS GARDEN CONTROLLER LISTO ===");
  Serial.println("Teclas: 1=Mov 2=Izq 3=Der 4=Frente 5=Atrás 6=Motor 7=L.Fuente 8=Camino 0=APAGAR");
}}

void loop() {{
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Sensores físicos
  bool pir = digitalRead(PIR_PIN) == HIGH;

  if (pir != last_pir) {{
    s_motion = pir;
    last_pir = pir;
    publishState();
  }}

  // Testing serial
  if (Serial.available() > 0) {{
    handleSerialInput(Serial.read());
  }}
  delay(50);
}}
"""
    return {"arduino_code": code}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "Warden Master Crew Online"}

@app.get("/api/esp/arduino")
async def get_arduino_code(ip: str = "192.168.1.131", broker_ip: str = "192.168.1.138"):
    """
    Genera el código C++ para el ESP32, configurado con la IP deseada y el broker MQTT.
    Incluye lógica para leer PIR y controlar un LED de Sirena vía MQTT.
    """
    code = f"""// Generado por Yarvis Edge Command Center
// Teclas en Serial Monitor para simular sensores:
//   1 = Mov. Frontal   2 = Mov. Trasero
//   3 = Laser 1        4 = Laser 2
//   5 = Acceso RF      6 = Sirena ON/OFF
#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid     = "TU_WIFI";
const char* password = "TU_PASSWORD";
const char* mqtt_server = "{broker_ip}";

const int SIREN_LED_PIN = 2; // LED integrado del ESP32

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// Estados de todos los sensores
bool s_motion_front = false;
bool s_motion_back  = false;
bool s_laser1       = false;
bool s_laser2       = false;
bool s_rf_access    = false;
bool s_siren        = false;

void setup_wifi() {{
  Serial.print("Conectando a WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {{ delay(500); Serial.print("."); }}
  Serial.println("");
  Serial.print("WiFi conectado. IP: ");
  Serial.println(WiFi.localIP());
}}

void publishState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]      = s_motion_front ? "active" : "standby";
  doc["motion_back"] = s_motion_back  ? "active" : "standby";
  doc["laser1"]      = s_laser1       ? "active" : "standby";
  doc["laser2"]      = s_laser2       ? "active" : "standby";
  doc["rf_access"]   = s_rf_access    ? "active" : "standby";
  doc["siren"]       = s_siren        ? "active" : "standby";
  char buffer[512];
  serializeJson(doc, buffer);
  mqtt.publish("finca/seguridad/patio/estado", buffer);
  Serial.print("[MQTT] Publicado: ");
  Serial.println(buffer);
}}

void callback(char* topic, byte* payload, unsigned int length) {{
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  if (String(topic) == "finca/seguridad/patio/siren/comando") {{
    DynamicJsonDocument doc(256);
    deserializeJson(doc, msg);
    String accion = doc["accion"];
    s_siren = (accion == "on");
    digitalWrite(SIREN_LED_PIN, s_siren ? HIGH : LOW);
    Serial.println(s_siren ? "SIRENA ACTIVADA" : "SIRENA DESACTIVADA");
    publishState();
  }}
}}

void reconnect() {{
  while (!mqtt.connected()) {{
    Serial.print("Intentando conexión MQTT...");
    if (mqtt.connect("ESP32_Patio_Client")) {{
      Serial.println("conectado");
      mqtt.subscribe("finca/seguridad/patio/siren/comando");
      publishState(); // Enviar estado inicial
    }} else {{
      Serial.print("falló, rc=");
      Serial.println(mqtt.state());
      delay(3000);
    }}
  }}
}}

void handleState() {{
  DynamicJsonDocument doc(512);
  doc["motion"]      = s_motion_front ? "active" : "standby";
  doc["motion_back"] = s_motion_back  ? "active" : "standby";
  doc["laser1"]      = s_laser1       ? "active" : "standby";
  doc["laser2"]      = s_laser2       ? "active" : "standby";
  doc["rf_access"]   = s_rf_access    ? "active" : "standby";
  doc["siren"]       = s_siren        ? "active" : "standby";
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}}

void handlePing() {{ server.send(200, "text/plain", "pong"); }}

void handleSerialInput(char key) {{
  switch (key) {{
    case '1': s_motion_front = !s_motion_front;
              Serial.println(s_motion_front ? "[1] Mov. Frontal: ACTIVO" : "[1] Mov. Frontal: INACTIVO");
              break;
    case '2': s_motion_back = !s_motion_back;
              Serial.println(s_motion_back ? "[2] Mov. Trasero: ACTIVO" : "[2] Mov. Trasero: INACTIVO");
              break;
    case '3': s_laser1 = !s_laser1;
              Serial.println(s_laser1 ? "[3] Laser 1: ACTIVO" : "[3] Laser 1: INACTIVO");
              break;
    case '4': s_laser2 = !s_laser2;
              Serial.println(s_laser2 ? "[4] Laser 2: ACTIVO" : "[4] Laser 2: INACTIVO");
              break;
    case '5': s_rf_access = !s_rf_access;
              Serial.println(s_rf_access ? "[5] Acceso RF: ACTIVO" : "[5] Acceso RF: INACTIVO");
              break;
    case '6': s_siren = !s_siren;
              digitalWrite(SIREN_LED_PIN, s_siren ? HIGH : LOW);
              Serial.println(s_siren ? "[6] Sirena: ACTIVO" : "[6] Sirena: INACTIVO");
              break;
    default:
      Serial.println("Teclas: 1=Mov.Frontal 2=Mov.Trasero 3=Laser1 4=Laser2 5=RF 6=Sirena");
      return; // No publicar si no es una tecla válida
  }}
  publishState(); // Publicar estado completo al Dashboard
}}

void setup() {{
  Serial.begin(115200);
  pinMode(SIREN_LED_PIN, OUTPUT);
  digitalWrite(SIREN_LED_PIN, LOW);
  setup_wifi();
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);
  server.on("/state", handleState);
  server.on("/ping", handlePing);
  server.begin();
  Serial.println("\\n=== YARVIS ESP32 LISTO ===");
  Serial.println("Teclas Serial: 1=MvFront 2=MvBack 3=Laser1 4=Laser2 5=RF 6=Sirena");
}}

void loop() {{
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Leer tecla del Serial Monitor
  if (Serial.available() > 0) {{
    char key = Serial.read();
    handleSerialInput(key);
  }}
  delay(50);
}}
"""
    return {"arduino_code": code}

if __name__ == "__main__":
    import uvicorn
    print("[Server] Iniciando Uvicorn en http://localhost:8000 ...")
    print("[Dashboard] Accede al panel web en: http://localhost:8000/ui/")
    uvicorn.run(app, host="0.0.0.0", port=8000)
