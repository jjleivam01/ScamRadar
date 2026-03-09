import streamlit as st
import sys
import os

# Asegurar que Python encuentra el paquete 'src'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.master.agent import WardenMasterCrew

st.set_page_config(page_title="Centinela Edge AI - The Warden", layout="wide")

# Instanciar el agente una sola vez en la sesión
@st.cache_resource
def get_warden():
    return WardenMasterCrew()

warden = get_warden()

st.title("🛡️ The Warden Command Center")
st.markdown("Interfaz de control central (Edge Processing) para la Finca El Banco.")

# Layout: dashboard a un lado, chat al otro
col_dash, col_chat = st.columns([1, 2])

with col_dash:
    st.subheader("📊 Estado del Ecosistema")
    st.info("Arquitectura: **Zero-Cloud / Orquestador Local**")
    
    st.metric("Sensor Puerta Principal", "Asegurado", "Normal")
    st.metric("Sistema de Visión", "Online", "+10 FPS")
    st.metric("Conexión LLM Local", "Standby / Fallback", "-")

    st.markdown("---")
    st.subheader("Últimos Eventos Edge MQTT")
    st.code('{"topic": "vision/puerta", "event": "reconocimiento", "status": "timeout_3m"}', language='json')
    st.code('{"topic": "sensores/pir", "event": "movimiento", "zone": "perimetro_norte"}', language='json')

with col_chat:
    st.subheader("💬 Comunicación Segura con The Warden")
    
    # Inicializar historial de chat
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Saludos, soy The Warden. El perímetro se encuentra monitoreado. ¿En qué te puedo ayudar?"}
        ]

    # Mostrar historial
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Entrada del usuario
    if prompt := st.chat_input("Escribe un comando o consulta para el Agente Master (Ej: 'Abre la puerta principal')..."):
        # Mostrar lo que escribió el usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Respuesta de The Warden
        with st.chat_message("assistant"):
            with st.spinner("The Warden está evaluando la situación analizando los sensores..."):
                response = warden.chat_with_warden(prompt)
                st.markdown(response)
                
        # Guardar en el historial
        st.session_state.messages.append({"role": "assistant", "content": response})