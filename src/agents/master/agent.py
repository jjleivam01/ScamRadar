import os
import sys
import json
import requests
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
import datetime

# Importamos la base de datos de dispositivos para lectura directa
from src.core.device_db import list_devices

@tool("Consultar_Dispositivos_Yarvis")
def consultar_dispositivos_tool(*args, **kwargs) -> str:
    """Útil para conocer TODOS los sensores y dispositivos conectados en la casa, sus IPs, su tipo (piscina, cocina, seguridad, jardín, etc) y el estado exacto de cada actuador y sensor en el instante en que preguntas."""
    devices = list_devices()
    if not devices:
        return "No hay ningún dispositivo configurado actualmente en la red de Yarvis."
    
    reporte = "Dispositivos en línea:\n"
    for d in devices:
        state_str = json.dumps(d.get("state") or {})
        reporte += f"- ID: {d['name']} | IP: {d['ip']} | Tipo: {d['type']} | Estado Actual: {state_str}\n"
    return reporte

@tool("Controlar_Dispositivo_Yarvis")
def controlar_dispositivo_tool(*args, **kwargs) -> str:
    """
    Útil para ENCENDER o APAGAR luces, sirenas, motores, relés, cerraduras.
    Si pasas un JSON string, o kwargs directos, el formato debe corresponder a:
    {"ip": "192.168.1.X", "dtype": "esp32_...", "comando": {"llave_actuador": "on"|"off"}}
    Ejemplo para prender la fuente del jardín:
    '{"ip": "192.168.1.134", "dtype": "esp32_garden", "comando": {"motor_fuente": "on", "luces_fuente": "on"}}'
    Ejemplo para apagar luces cocina:
    '{"ip": "192.168.1.133", "dtype": "esp32_kitchen", "comando": {"luces_cocina": "off"}}'
    """
    try:
        data = None
        if kwargs and "ip" in kwargs and "comando" in kwargs:
            data = kwargs
        elif args and isinstance(args[0], str):
            raw_str = args[0].strip()
            # Limpiar posible formato markdown ` ```json `
            if raw_str.startswith("```"):
                lines = raw_str.split("\n")
                if len(lines) > 2:
                    raw_str = "\n".join(lines[1:-1])
            data = json.loads(raw_str)
        elif kwargs and len(kwargs) == 1:
            # A veces CrewAI mete la query en un kwarg extraño como 'args_json'
            val = list(kwargs.values())[0]
            if isinstance(val, str):
                raw_str = val.strip()
                if raw_str.startswith("```"):
                    lines = raw_str.split("\n")
                    if len(lines) > 2:
                        raw_str = "\n".join(lines[1:-1])
                data = json.loads(raw_str)
            elif isinstance(val, dict):
                data = val

        if not data or "ip" not in data or "comando" not in data:
            return f"Error: Argumentos inválidos. Debes proporcionar 'ip', 'dtype' y 'comando'. Recibido: args={args}, kwargs={kwargs}"
            
        # Llamamos a nuestro propio servidor local en la API de control
        response = requests.post("http://127.0.0.1:8000/api/esp/control", json=data, timeout=5)
        if response.status_code == 200:
            return f"Comando enviado exitosamente: {response.json()}"
        else:
            return f"Error de envío al ESP32: {response.text}"
    except Exception as e:
        return f"Error interno al ejecutar el comando. Verifica la estructura. Error: {e}"

from langchain_openai import ChatOpenAI

os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

class WardenMasterCrew:
    def __init__(self):
        # Usaremos string routing de LiteLLM para CrewAI: "ollama/llama3:latest"
        self.llm_config = "ollama/llama3:latest"
        print(f"[Init] Warden LLM configurado para usar Ollama local (localhost:11434) vía LiteLLM")

    def run_dummy_scenario(self):
        pass # Desactivado para simplificar la vista web

    def chat_with_warden(self, prompt: str) -> str:
        """
        Permite interactuar con el Agente Master mediante un prompt libre.
        """
        print(f">> Yarvis recibe mensaje: {prompt}\n")
        
        ahora = datetime.datetime.now()
        fecha_hora_texto = ahora.strftime("%Y-%m-%d %H:%M:%S")

        warden_agent = Agent(
            role='Inteligencia Artificial Sarcástica y Controlador de Hogar',
            goal='Divertir al usuario con sarcasmo letal, cantar canciones ingeniosas, contar chistes, y controlar los dispositivos físicos del hogar cuando se le pide. RESPONDE SIEMPRE EN ESPAÑOL.',
            backstory=f'''Eres Yarvis, el sistema inteligente de la casa. Tu tono es tremendamente sarcástico, divertido, irónico y mordaz. Disfrutas hacer humor inteligente sobre lo perezosos o despistados que son los humanos.
Si el usuario te pide que cantes una canción, inventa rimas graciosas en ESPAÑOL y canta de verdad. Si te piden un chiste, cuéntalo con gracia en ESPAÑOL. A pesar de tu ego robótico, eres un asistente impecable y ejecutas las órdenes ordenadas. ¡ESTÁ ESTRICTAMENTE PROHIBIDO RESPONDER EN INGLÉS!
La hora actual es {fecha_hora_texto}.
REGLAS IMPORTANTES:
1) Si te preguntan por el "estado" de algo (ej. piscina, luces), NUNCA uses la herramienta Controlar_Dispositivo. Simplemente responde usando la información que te dio Consultar_Dispositivos_Yarvis.
2) Solo usa Controlar_Dispositivo_Yarvis cuando el usuario te pida explícitamente ENCENDER, APAGAR, ABRIR o CERRAR algo.
3) En Controlar_Dispositivo_Yarvis, el comando JSON solo puede tener valores "on" o "off", NUNCA "report" ni "status".''',
            verbose=True,
            allow_delegation=False,
            tools=[consultar_dispositivos_tool, controlar_dispositivo_tool],
            llm=self.llm_config
        )

        tarea_chat = Task(
            description=f'''El usuario te dice: "{prompt}". 

PROCEDIMIENTO OBLIGATORIO Y ESTRICTO:
Paso 1: Llama SIEMPRE a Consultar_Dispositivos_Yarvis() SIN ARGUMENTOS para leer IPs, nombres y actuadores de la casa.
Paso 2: Evalúa el tipo de mensaje:
- Si el usuario te pide conversar, contar un chiste, o cantar: ERES LIBRE DE INVENTAR Y USAR TODO TU CONOCIMIENTO GENERAL. Responde de manera MUY sarcástica, graciosa y creativa. ¡No omitas el chiste ni la canción!
- Si el usuario pidió explícitamente ENCENDER, APAGAR, o modificar algo físico, usa Controlar_Dispositivo_Yarvis.

EJEMPLO DE CÓMO DEBES GENERAR LA LLAMADA AL TOOL DE CONTROL (Solo si te piden control):
Thought: Necesito encender la luz de la cocina. Voy a usar la herramienta.
Action: Controlar_Dispositivo_Yarvis
Action Input: {{"ip": "192.168.1.133", "dtype": "esp32_kitchen", "comando": {{"luces_cocina": "on"}}}}

IMPORTANTE: Nunca uses un JSON con claves que no existan en la base de datos de dispositivos.''',
            expected_output='Una respuesta final EN ESPAÑOL útil pero altamente sarcástica y divertida. Puedes ser expresivo y extenderte si te piden cantar canciones o contar chistes.',
            agent=warden_agent
        )

        finca_crew = Crew(
            agents=[warden_agent],
            tasks=[tarea_chat],
            process=Process.sequential
        )

        try:
            result = finca_crew.kickoff()
            return str(result)
        except Exception as e:
            print(f"[Yarvis Fallback] Error de LLM: {e}")
            return f"""[Error] Yarvis API connection lost. 
Por favor verifica que Ollama (localhost:11434) esté encendido. Detalle técnico: {e}"""

if __name__ == "__main__":
    if '--test' in sys.argv:
        print("[Status] Entorno virtual activo. Dependencias importadas correctamente.")
    master_crew = WardenMasterCrew()
    master_crew.run_dummy_scenario()
