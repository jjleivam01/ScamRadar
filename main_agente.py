import streamlit as st
from langchain_openai import ChatOpenAI
import paho.mqtt.client as mqtt

# Configuración del LLM Local (LM Studio)
llm = ChatOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio",
    temperature=0.1 # Rigor técnico para la tesis
)

st.title("🛡️ Centinela AI - Control Center")
st.write(f"Directorio de Tesis: `C:\\Tesis_IA`")

# Interfaz para visualizar eventos en tiempo real
if "eventos" not in st.session_state:
    st.session_state.eventos = []

def al_recibir_mensaje(client, userdata, msg):
    evento = msg.payload.decode()
    st.session_state.eventos.append(f"🚨 Alerta: {evento}")
    # Aquí es donde el agente "piensa" sobre el evento
    if "movimiento" in evento:
        respuesta = llm.predict("Se detectó movimiento en la puerta de la casa en El Banco. Genera un protocolo de seguridad breve.")
        st.session_state.eventos.append(f"🤖 Agente: {respuesta}")

# Configuración MQTT simplificada para prueba local
client = mqtt.Client()
client.on_message = al_recibir_mensaje

# Botón para simular el sensor de la puerta (mientras conectamos el hardware)
if st.button("Simular Sensor Puerta (MQTT)"):
    al_recibir_mensaje(None, None, type('obj', (object,), {'payload': b'movimiento_detectado_puerta_principal'}))

for ev in reversed(st.session_state.eventos):
    st.info(ev)