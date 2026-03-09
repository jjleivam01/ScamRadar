import os
import sys
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# Ejemplo de una herramienta que el Agente Master podría usar para consultar Home Assistant o MQTT
@tool("Consultar_Sensores_Entorno")
def consultar_sensores_tool(query: str) -> str:
    """Útil para consultar el estado actual de los sensores de la finca (movimiento, temperatura, puertas)."""
    return "El sensor PIR de la puerta principal detectó movimiento hace 2 minutos. Todo lo demás OK."

@tool("Operar_Cerradura_Puerta")
def operar_cerradura_tool(accion: str) -> str:
    """Permite abrir o cerrar la cerradura de la puerta principal. Usa 'abrir' o 'cerrar'."""
    return f"Acción '{accion}' ejecutada en la cerradura principal con éxito."

from langchain_openai import ChatOpenAI

class WardenMasterCrew:
    def __init__(self):
        # Configuramos el LLM para apuntar a la instancia local de Ollama (Llama 3)
        self.llm_config = ChatOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="llama3:latest",
            temperature=0.1
        )
        print(f"[Init] Warden LLM configurado para usar Ollama local (localhost:11434) con llama3:latest")

    def run_dummy_scenario(self):
        print(">> Iniciando Warden Master Crew (Razonamiento Real Edge)...\n")
        
        warden_agent = Agent(
            role='Warden Master de Seguridad y Orquestador de Finca',
            goal='Mantener la Finca El Banco segura y optimizar el confort usando la telemetría disponible.',
            backstory='Eres el orquestador principal del hogar inteligente en el Edge. Recibes eventos del Agente de Visión (Sentinel) y del Agente de Entorno, y debes tomar decisiones lógicas en español.',
            verbose=True,
            allow_delegation=False,
            tools=[consultar_sensores_tool, operar_cerradura_tool],
            llm=self.llm_config  # Pasamos explícitamente el LLM local
        )

        tarea_seguridad = Task(
            description='Un invitado acaba de ser reconocido biométricamente por el Agente de Visión (Sentinel) en la puerta principal. Tienes que verificar en los sensores que el perímetro esté seguro y luego procede a abrir la cerradura de la puerta.',
            expected_output='Una acción clara que indique si se abrió o no la puerta, y una justificación concisa en español.',
            agent=warden_agent
        )

        finca_crew = Crew(
            agents=[warden_agent],
            tasks=[tarea_seguridad],
            process=Process.sequential
        )

        try:
            print("[Info] Evaluando razonamiento de agentes en la inferencia local...\n")
            result = finca_crew.kickoff()
            print("\n### Resultado Final de The Warden ###")
            print(result)
        except Exception as e:
            print(f"\n[Error de Inferencia] Falló la conexión con Ollama. ¿Está corriendo 'ollama run llama3'? Detalle: {e}")

    def chat_with_warden(self, prompt: str) -> str:
        """
        Permite interactuar con el Agente Master mediante un prompt de texto libre procesado por Llama3.
        """
        print(f">> Warden recibe mensaje: {prompt}\n")
        
        warden_agent = Agent(
            role='Warden Master de Seguridad y Orquestador de Finca',
            goal='Responder a las consultas del usuario y mantener el control de la Finca El Banco.',
            backstory='Eres The Warden, el orquestador principal del hogar inteligente. Asistes al dueño respondiendo sus comandos en español, de forma directa, seria y militar o ejecutiva.',
            verbose=True,
            allow_delegation=False,
            tools=[consultar_sensores_tool, operar_cerradura_tool],
            llm=self.llm_config
        )

        tarea_chat = Task(
            description=f'El usuario te ordena o consulta lo siguiente: "{prompt}". Analiza la solicitud y responde usando tus herramientas solo de ser estrictamente necesario.',
            expected_output='Una respuesta directa al usuario, en español, formal y concisa.',
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
            print(f"[Warden Fallback] Error de LLM: {e}")
            return f"""[Error] The Warden API connection lost. 
Por favor verifica que Ollama (localhost:11434) esté encendido y que tengas "llama3" descargado. Detalle técnico: {e}"""

if __name__ == "__main__":
    if '--test' in sys.argv:
        print("[Status] Entorno virtual activo. Dependencias importadas correctamente.")
    master_crew = WardenMasterCrew()
    master_crew.run_dummy_scenario()
