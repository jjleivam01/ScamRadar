from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Asegurar que el backend encuentre los módulos internos de la Tesis
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.agents.master.agent import WardenMasterCrew

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

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Recibe un prompt del frontend web, se lo pasa a CrewAI, y devuelve la respuesta.
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    
    # Procesar con el Master Agent
    try:
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

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "agent": "Warden Master Crew Online"}
