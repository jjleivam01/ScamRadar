document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const messagesArea = document.getElementById('chat-messages');
    const btnLock = document.getElementById('btn-lock');
    const btnSentinel = document.getElementById('btn-sentinel');
    const mqttTerminal = document.getElementById('mqtt-terminal');

    // Función para añadir mensaje a la UI
    function addMessage(text, role) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', role);

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('avatar');

        if (role === 'assistant') {
            avatarDiv.innerHTML = '<i class="ph-fill ph-robot"></i>';
        } else if (role === 'system-alert') {
            avatarDiv.innerHTML = '<i class="ph-fill ph-warning"></i>';
        } else {
            avatarDiv.innerHTML = '<i class="ph-fill ph-user"></i>';
        }

        const bubbleDiv = document.createElement('div');
        bubbleDiv.classList.add('bubble');

        // Formateo muy básico de saltos de línea y negritas (Opcional, se puede mejorar con un Markdown parser real)
        let formattedText = text.replace(/\n/g, '<br>');
        formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bubbleDiv.innerHTML = formattedText;

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(bubbleDiv);

        messagesArea.appendChild(msgDiv);

        // Auto-scroll al final
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // Añadir log falso MQTT
    function addMqttLog(module, text) {
        const p = document.createElement('p');
        const now = new Date();
        const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}]`;
        p.innerHTML = `<span class="time">${timeStr}</span> [${module}] ${text}`;
        mqttTerminal.appendChild(p);
        mqttTerminal.scrollTop = mqttTerminal.scrollHeight;
    }

    // Manejar Envío de Formulario
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const text = chatInput.value.trim();
        if (!text) return;

        // 1. Mostrar user message
        addMessage(text, 'user');
        chatInput.value = '';
        chatInput.disabled = true;

        // 2. Mostrar un "indicador de escribiendo"
        const typingId = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.id = typingId;
        typingDiv.classList.add('message', 'assistant', 'typing-indicator');
        typingDiv.innerHTML = `
            <div class="avatar"><i class="ph-fill ph-robot"></i></div>
            <div class="bubble">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
        `;
        messagesArea.appendChild(typingDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;

        addMqttLog('warden', `Recibido comando: "${text.substring(0, 20)}..." Evaluando...`);

        // 3. Peición a FastAPI Backend
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) {
                throw new Error("API devovió error " + response.status);
            }

            const data = await response.json();

            // Remover typing
            document.getElementById(typingId).remove();

            // Pintar respuesta real
            addMessage(data.reply, 'assistant');
            addMqttLog('warden', `Respuesta enviada (${data.reply.length} chars)`);

        } catch (error) {
            console.error("Fetch error:", error);
            document.getElementById(typingId).remove();
            addMessage(`[Error de Conexión HTTP] No me pude comunicar con el Backend FastAPI. Revisa que el servidor Python esté escuchando.\nDetalle: ${error.message}`, 'system-alert');
            addMqttLog('system', `<span style="color:#ff6b6b">API Error: ${error.message}</span>`);
        } finally {
            chatInput.disabled = false;
            chatInput.focus();
        }
    });

    // Lockdown Button Mock
    let isLocked = false;
    btnLock.addEventListener('click', () => {
        const appContainer = document.querySelector('.app-container');
        if (!isLocked) {
            isLocked = true;
            appContainer.classList.add('lockdown-mode');
            addMessage("⚠️ Iniciando **Protocolo Cero** (Bloqueo Total). Todas las puertas perimetrales han sido aseguradas. El Agente Sentinel Vision ha sido elevado a Prioridad 1 y se cancelan tokens MQTT salientes externos.", 'system-alert');
            addMqttLog('warden', '<strong style="color:var(--danger)">EJECUTANDO PROTOCOLO CERO</strong>');
            document.querySelectorAll('.metric-value').forEach(el => {
                if (el.innerText !== "Running - 32 FPS") {
                    el.style.color = 'var(--danger)';
                    el.innerText = 'LOCKED';
                }
            });
            btnLock.innerHTML = '<i class="ph-fill ph-lock-key-open"></i> Desbloquear';
        } else {
            isLocked = false;
            appContainer.classList.remove('lockdown-mode');
            addMessage("Protocolo Cero levantado. Volviendo a modo seguro.", 'assistant');
            addMqttLog('warden', '<span style="color:var(--success)">Protocolo de emergencia levantado</span>');
            btnLock.innerHTML = '<i class="ph ph-lock-key"></i> Protocolo Cero';
        }
    });

    // Activar Sentinel Vision Pipeline
    btnSentinel.addEventListener('click', async () => {
        addMessage("Conectando con el Agente Sentinel Vision. Iniciando feed de cámara web en el Edge Server...", 'assistant');
        addMqttLog('warden', "Lanzando hilo: src/agents/vision/sentinel.py");

        try {
            const response = await fetch('/api/sentinel', {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error("API devovió error al activar cámara " + response.status);
            }

            const data = await response.json();
            addMqttLog('vision', `<span style="color:var(--success)">${data.status}</span>`);

        } catch (error) {
            console.error("Fetch error Sentinel:", error);
            addMessage(`[Error Sentinel] No se pudo lanzar el stream de video. ${error.message}`, 'system-alert');
        }
    });

    // Ponerle foco al input al cargar
    chatInput.focus();
});
