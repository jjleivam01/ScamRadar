# Arquitectura del Ecosistema de Agentes Cognitivos para el Edge

## 1. Visión General
Este documento describe la arquitectura para un ecosistema personalizado de agentes de IA optimizado para procesamiento en el Edge (Edge Computing). Prescindimos de dependencias externas como Home Assistant para mantener el control total del flujo de datos, la latencia, la seguridad y la orquestación.

## 2. Topología de Hardware
*   **Servidor Edge Central (The Warden):**
    *   **CPU:** Intel Core i7
    *   **GPU:** NVIDIA RTX 4070 (12GB VRAM) - Fundamental para la ejecución local de LLMs cuantizados (razonamiento) y modelos de Visión en paralelo.
    *   **RAM:** 32GB
*   **Nodos Sensores/Actuadores:** Microcontroladores ESP32 comunicándose vía MQTT.
*   **Sistema de Visión:**
    *   **Cámara Principal (Acceso/Puerta):** Conexión **cableada** (Ethernet/USB) obligatoria. Garantiza la calidad de imagen óptima (sin artefactos de compresión Wi-Fi) y baja latencia, requisitos indispensables para el reconocimiento facial continuo de visitantes.
    *   **Cámaras Secundarias (Perímetro/Piscina):** Conexión Wi-Fi (RTSP/WebRTC) reservadas para análisis de detección de objetos genéricos (vehículos, personas, caídas), donde la pérdida ocasional de paquetes es tolerable.

## 3. Arquitectura de Software y Agentes (Ecosistema Propio)
El ecosistema se compone de agentes especializados, operados en Python, que se comunican de forma asíncrona mediante un bus de eventos (MQTT).

### 3.1 Agente Master (The Warden)
*   **Rol:** Orquestador central y toma de decisiones cognitivas.
*   **Tecnología:** LangChain / CrewAI operando sobre un LLM local cuantizado (Llama 3 8B o Mistral).
*   **Responsabilidades:** Procesar eventos críticos de todos los agentes. Mantener el contexto general del hogar, gestionar reglas de conflicto (ej., priorizar seguridad perimetral sobre tareas de confort) y disparar secuencias de mitigación (bloqueo de accesos, alertas visuales/sonoras).

### 3.2 Agente de Percepción Visual (Sentinel Vision)
*   **Rol:** Extracción de telemetría e inferencia a partir de video en tiempo real.
*   **Tecnología:** OpenCV, YOLOv10 (detección de intrusos/vehículos/anomalías) y DeepFace/FaceNet (reconocimiento facial de alta precisión).
*   **Procesamiento:**
    *   **Pipeline Cableado:** Analiza continuamente el acceso principal buscando coincidencias biométricas contra una base de datos local y publicando veredictos de acceso (Access Granted / Access Denied).
    *   **Pipeline Inalámbrico:** Monitorea las cámaras secundarias para disparar alertas preventivas de presencia (humana o vehicular).

### 3.3 Agente de Interacción Natural (Voice Interface)
*   **Rol:** Interfaz conversacional y procesamiento de lenguaje natural (Voz).
*   **Tecnología:** Faster-Whisper (STT ultrarrápido) y Llama 3 / Piper (TTS local).
*   **Responsabilidades:** Servir de interfaz sin fricción para el usuario de manera 100% offline. Traducir comandos audibles a instrucciones para The Warden y sintetizar alertas verbales.

### 3.4 Agente de Control de Entorno (Comfort & Maintenance)
*   **Rol:** Puente de actuación hacia el hardware físico.
*   **Tecnología:** Clientes MQTT ligeros (Paho-MQTT Python).
*   **Responsabilidades:** Suscribirse a los tópicos de control para accionar relés (luces, portones, climatización) ordenados por el Master, y recopilar de manera continua la telemetría sensórica de los ESP32 (temperatura, presencia PIR) para historización y contexto.

## 4. Middleware y Orquestación Backend
*   **Protocolo de Orquestación Interna:** MQTT local (Broker Mosquitto) y un sistema de colas / APIs REST internas (FastAPI) para payloads pesados o sincronización bloqueante entre agentes.
*   **Formatos y Eventos:** Todo intercambio de estado se realiza en formato estándar JSON sobre tópicos bien definidos (ej., `finca/vision/puerta/rostro`, `finca/master/comandos`).

## 5. Estado Actual de Implementación (Progreso)
Hasta la fecha, se ha avanzado en la construcción del esqueleto central y la orquestación de la arquitectura:

*   **Estructura del Proyecto Configurada:**
    *   `src/agents/`: Contenedor principal de los agentes por dominio lógico (`master`, `vision`, `voice`, `environment`).
    *   `src/api/`: Capa de integración backend mediante FastAPI.
    *   `public/`: Capa de presentación e interfaz web (HTML/CSS/JS).
*   **Agente Master (The Warden) Funcional:**
    *   Construido sobre `CrewAI` y `LangChain`.
    *   Integración exitosa con **Ollama local (Llama 3)**, garantizando inferencia y toma de decisiones offline.
    *   Herramientas (`tools`) iniciales configuradas (simulador de sensores y cerradura).
*   **Backend y API (FastAPI):**
    *   Servidor operativo en `server.py` que expone endpoints como `/api/chat` para hablar con The Warden y `/api/sentinel` para levantar el pipeline de visión como subproceso aislado.
*   **Dependencias y Setup:**
    *   Archivo `requirements.txt` estructurado con la base de orquestación y API, omitiendo paquetes pesados de visión/voz hasta que entren formalmente en desarrollo intensivo.

### Próximos Pasos Recomendados (Roadmap Inmediato)
1.  **Desarrollo Fuerte de Visión:** Finalizar el script de Sentinel Vision (OpenCV + FaceNet/YOLO) para procesar webcams en tiempo real.
2.  **Infraestructura MQTT:** Instalar y lanzar un broker Mosquitto local para iniciar simulaciones asíncronas entre The Warden y el Entorno.
3.  **Interfaz de Voz:** Integrar Faster-Whisper para procesar instrucciones audibles de forma local.
