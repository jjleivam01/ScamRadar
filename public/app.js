document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const messagesArea = document.getElementById('chat-messages');
    const btnLock = document.getElementById('btn-lock');
    const btnSentinel = document.getElementById('btn-sentinel');
    const btnVoice = document.getElementById('btn-voice');
    const mqttTerminal = document.getElementById('mqtt-terminal');
    const selectMode = document.getElementById('select-mode');

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

        let formattedText = text.replace(/\n/g, '<br>');
        formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bubbleDiv.innerHTML = formattedText;

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(bubbleDiv);

        messagesArea.appendChild(msgDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // Añadir log MQTT
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

        addMessage(text, 'user');
        chatInput.value = '';
        chatInput.disabled = true;

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

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) throw new Error("API devovió error " + response.status);
            const data = await response.json();
            document.getElementById(typingId).remove();
            addMessage(data.reply, 'assistant');
        } catch (error) {
            document.getElementById(typingId).remove();
            addMessage(`[Error] No me pude comunicar con el Backend. ${error.message}`, 'system-alert');
        } finally {
            chatInput.disabled = false;
            chatInput.focus();
        }
    });

    // Lockdown
    let isLocked = false;
    btnLock.addEventListener('click', () => {
        const appContainer = document.querySelector('.app-container');
        if (!isLocked) {
            isLocked = true;
            appContainer.classList.add('lockdown-mode');
            addMessage("⚠️ Iniciando **Protocolo Cero**. Perímetros asegurados.", 'system-alert');
            btnLock.innerHTML = '<i class="ph-fill ph-lock-key-open"></i> Desbloquear';
        } else {
            isLocked = false;
            appContainer.classList.remove('lockdown-mode');
            addMessage("Protocolo Cero levantado.", 'assistant');
            btnLock.innerHTML = '<i class="ph ph-lock-key"></i> Protocolo Cero';
        }
    });

    // Sentinel Vision
    btnSentinel.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/sentinel', { method: 'POST' });
            if (!response.ok) throw new Error("API Error");
            const data = await response.json();
            addMqttLog('vision', `<span style="color:var(--success)">${data.status}</span>`);
        } catch (error) {
            addMessage(`[Error Sentinel] ${error.message}`, 'system-alert');
        }
    });

    // Voice Agent
    let voiceWs = null;
    if (btnVoice) {
        btnVoice.addEventListener('click', () => {
            if (voiceWs) { voiceWs.close(); return; }
            const loadingBar = document.getElementById('voice-loading-bar');
            if (loadingBar) loadingBar.classList.remove('hidden');
            btnVoice.innerHTML = '<i class="ph-bold ph-spinner-gap spin"></i> Cargando...';
            btnVoice.disabled = true;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            voiceWs = new WebSocket(`${protocol}//${window.location.host}/api/ws/voice`);

            voiceWs.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'log' && (data.text.includes("EN MODO ESCUCHA") || data.text.includes("YARVIS VOICE INTERFACE") || data.text.includes("[STT] YARVIS VOICE INTERFACE"))) {
                    if (loadingBar) loadingBar.classList.add('hidden');
                    btnVoice.disabled = false;
                    btnVoice.classList.add('pulse-mic');
                    btnVoice.innerHTML = '<i class="ph-fill ph-microphone"></i> Detener Voz';
                } else if (data.type === 'log') {
                    addMqttLog(data.source || 'server', data.text);
                } else if (data.type === 'system_mode') {
                    if (selectMode) {
                        selectMode.value = data.mode;
                        addMqttLog('system', `Modo sincronizado externamente: **${data.mode}**`);
                    }
                } else if (data.type === 'user_msg') {
                    addMessage(data.text, 'user');
                } else if (data.type === 'assistant_msg') {
                    addMessage(data.text, 'assistant');
                }
            };
            voiceWs.onclose = () => {
                voiceWs = null;
                if (loadingBar) loadingBar.classList.add('hidden');
                btnVoice.disabled = false;
                btnVoice.classList.remove('pulse-mic');
                btnVoice.innerHTML = '<i class="ph ph-microphone"></i> Activar Voz';
            };
        });
    }

    // Selector de Modos de Sistema
    if (selectMode) {
        selectMode.addEventListener('change', async () => {
            const mode = selectMode.value;
            try {
                const response = await fetch('/api/system/mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: mode })
                });

                if (!response.ok) throw new Error("Error en el servidor");
                const data = await response.json();
                
                // Mostrar respuesta de Yarvis en el chat
                addMessage(data.reply, 'assistant');
                
                // Efecto visual temporal en el selector
                selectMode.style.borderColor = 'var(--success)';
                setTimeout(() => selectMode.style.borderColor = 'var(--panel-border)', 2000);
                
                addMqttLog('system', `Modo cambiado a: **${mode}**`);
            } catch (error) {
                addMessage(`[Error Modo] No se pudo activar el modo ${mode}.`, 'system-alert');
            }
        });
    }

    // Hologram 360
    const hologramModal = document.getElementById('hologram-modal');
    const closeHologramBtn = document.getElementById('close-hologram');
    const hologramImage = document.getElementById('hologram-image');
    const hologramContainer = document.getElementById('hologram-container');

    const hologramTrigger = document.getElementById('hologram-trigger');
    if (hologramTrigger) hologramTrigger.addEventListener('click', () => hologramModal.classList.remove('hidden'));
    if (closeHologramBtn) closeHologramBtn.addEventListener('click', () => hologramModal.classList.add('hidden'));

    let currentImg = 1;
    let isDragging = false;
    let startX = 0;
    if (hologramContainer) {
        hologramContainer.addEventListener('mousedown', (e) => { isDragging = true; startX = e.clientX; });
        window.addEventListener('mouseup', () => isDragging = false);
        hologramContainer.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            if (Math.abs(dx) > 15) {
                if (dx > 0) currentImg--; else currentImg++;
                if (currentImg < 1) currentImg = 12; if (currentImg > 12) currentImg = 1;
                hologramImage.src = `assets/fotocasa/${currentImg}.jpg`;
                startX = e.clientX;
            }
        });
    }

    // -----------------------------------------
    // GESTIÓN DE DISPOSITIVOS ESP32
    // -----------------------------------------
    const btnAddEsp = document.getElementById('btn-add-esp');
    const espIpInput = document.getElementById('esp-ip-input');
    const patioPanel = document.getElementById('patio-security-panel');
    const closeSecurityBtn = document.getElementById('close-security');

    if (btnAddEsp) {
        btnAddEsp.addEventListener('click', async () => {
            const ip = espIpInput.value.trim();
            if (!ip) return;
            btnAddEsp.disabled = true;
            btnAddEsp.innerHTML = '<i class="ph-bold ph-spinner-gap spin"></i>';

            try {
                const response = await fetch('/api/esp/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ip: ip })
                });
                const data = await response.json();
                if (data.status === 'success') {
                    addMessage(`Dispositivo **${data.device}** vinculado en ${ip}.`, 'assistant');
                    patioPanel.classList.remove('hidden');
                    renderConnectedDevice(ip, data.device);
                    if (data.state) updateSecurityUI(data.state);

                    // Polling directo al ESP32 cada 2 segundos (independiente del MQTT WebSocket)
                    startEspPolling(ip);
                } else {
                    addMessage(`Error: ${data.message}`, 'system-alert');
                }
            } catch (error) {
                addMessage(`Error Backend: ${error.message}`, 'system-alert');
            } finally {
                btnAddEsp.disabled = false;
                btnAddEsp.innerHTML = '<i class="ph ph-plus"></i>';
            }
        });
    }

    let espPollingInterval = null;
    function startEspPolling(ip) {
        if (espPollingInterval) clearInterval(espPollingInterval);
        espPollingInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/esp/state?ip=${ip}`);
                const state = await resp.json();
                if (!state.error) {
                    updateSecurityUI(state);
                }
            } catch (e) { /* silencioso */ }
        }, 2000); // Cada 2 segundos
    }

    // Toggle for Add ESP section
    const toggleAddEspBtn = document.getElementById('toggle-add-esp');
    const addEspContent = document.getElementById('add-esp-content');
    if (toggleAddEspBtn && addEspContent) {
        let isAddEspVisible = true;
        toggleAddEspBtn.addEventListener('click', () => {
            isAddEspVisible = !isAddEspVisible;
            if (isAddEspVisible) {
                addEspContent.style.display = 'flex';
                toggleAddEspBtn.innerHTML = '<i class="ph-bold ph-minus"></i>';
            } else {
                addEspContent.style.display = 'none';
                toggleAddEspBtn.innerHTML = '<i class="ph-bold ph-plus"></i>';
            }
        });
    }

    // Render Connected Device Card in Sidebar
    function renderConnectedDevice(ip, deviceName) {
        const section = document.getElementById('connected-devices-section');
        const list = document.getElementById('devices-list');
        if (!section || !list) return;

        section.style.display = 'block';

        // Check if already exists
        if (document.getElementById(`sidebar-device-${ip}`)) return;

        const card = document.createElement('div');
        card.id = `sidebar-device-${ip}`;
        card.className = 'metric-card';
        card.style.cursor = 'pointer';
        card.innerHTML = `
            <div class="metric-top">
                <i class="ph ph-cpu"></i>
                <span>${deviceName}</span>
            </div>
            <div class="metric-value status-online" style="font-size: 11px;">IP: ${ip}</div>
        `;

        // Open the security modal when clicked
        card.addEventListener('click', () => {
            const patioPanel = document.getElementById('patio-security-panel');
            if (patioPanel) patioPanel.classList.remove('hidden');
        });

        list.appendChild(card);
    }

    if (closeSecurityBtn) closeSecurityBtn.addEventListener('click', () => patioPanel.classList.add('hidden'));

    function updateSecurityUI(states) {
        // Mapeo de claves del ESP32 → IDs de tarjetas en el HTML
        const KEY_MAP = {
            'motion': 'motion_front',
            'motion_front': 'motion_front',
            'motion_back': 'motion_back',
            'laser1': 'laser_perim_1',
            'laser_perim_1': 'laser_perim_1',
            'laser2': 'laser_perim_2',
            'laser_perim_2': 'laser_perim_2',
            'rf': 'rf_access',
            'rf_access': 'rf_access',
            'siren': 'siren',
        };

        for (const [rawKey, value] of Object.entries(states)) {
            const id = KEY_MAP[rawKey] || rawKey;
            const card = document.getElementById(`sensor-${id}`);
            if (card) {
                const isActive = (value === 'active' || value === 'ON' || value === true);
                if (isActive) card.classList.add('active'); else card.classList.remove('active');
                const indicator = card.querySelector('.status-indicator');
                if (indicator) indicator.innerText = isActive ? 'Activo' : 'Inactivo';
                if (id === 'siren') {
                    const btn = document.getElementById('btn-toggle-siren-ui');
                    if (btn) {
                        if (isActive) { card.classList.add('on'); btn.innerText = 'Desactivar'; }
                        else { card.classList.remove('on'); btn.innerText = 'Activar'; }
                    }
                }
            }
        }
    }

    const btnSirenUI = document.getElementById('btn-toggle-siren-ui');
    if (btnSirenUI) {
        btnSirenUI.addEventListener('click', async () => {
            const sirenCard = document.getElementById('sensor-siren');
            const isCurrentlyOn = sirenCard && sirenCard.classList.contains('on');
            const action = isCurrentlyOn ? 'off' : 'on';

            try {
                const resp = await fetch('/api/esp/siren', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ accion: action })
                });
                const data = await resp.json();
                if (data.status === 'ok') {
                    // Actualizar la UI de forma inmediata (sin esperar MQTT)
                    if (action === 'on') {
                        sirenCard.classList.add('on', 'active');
                        btnSirenUI.innerText = 'Desactivar';
                    } else {
                        sirenCard.classList.remove('on', 'active');
                        btnSirenUI.innerText = 'Activar';
                    }
                    addMqttLog('sirena', `Comando enviado: ${action.toUpperCase()}`);
                } else {
                    addMessage(`[Error Sirena] ${data.message}`, 'system-alert');
                }
            } catch (e) {
                addMessage(`[Error Sirena] ${e.message}`, 'system-alert');
            }
        });
    }

    // Telemetría MQTT
    function initMqttStream() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const mqttWs = new WebSocket(`${protocol}//${window.location.host}/api/ws/mqtt`);
        mqttWs.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // Actualización de estado en tiempo real (sensores)
            if (data.topic === 'finca/seguridad/patio/estado') {
                updateSecurityUI(data.payload);
            }
            // Eventos de conexión del dispositivo (Heartbeat)
            else if (data.topic === 'finca/seguridad/patio/conexion') {
                handleDeviceConnection(data.payload);
            }
            // Sincronización de modo global (desde Topic MQTT)
            else if (data.topic === 'finca/sistema/modo') {
                const mode = data.payload.mode;
                if (selectMode && mode) {
                    selectMode.value = mode;
                    addMqttLog('system', `Sincr. Global: **${mode}**`);
                    
                    // Efecto visual en el selector
                    selectMode.style.borderColor = 'var(--accent)';
                    setTimeout(() => selectMode.style.borderColor = 'var(--panel-border)', 1500);
                }
            }
            // Sincronización de modo de sistema (desde Evento Directo WebSocket)
            else if (data.type === 'system_mode') {
                if (selectMode) {
                    selectMode.value = data.mode;
                    addMqttLog('system', `Modo sincronizado: **${data.mode}**`);
                    
                    // Efecto visual en el selector
                    selectMode.style.borderColor = 'var(--accent)';
                    setTimeout(() => selectMode.style.borderColor = 'var(--panel-border)', 1500);
                }
            }

            if (data.topic) {
                addMqttLog(data.topic.split('/')[1] || data.topic, JSON.stringify(data.payload));
            }
        };
        mqttWs.onclose = () => setTimeout(initMqttStream, 5000);
    }

    function handleDeviceConnection(payload) {
        // payload = {ip: "...", event: "offline" | "reconnected", timestamp: "..."}
        const patioPanel = document.getElementById('patio-security-panel');
        if (!patioPanel) return;

        if (payload.event === 'offline') {
            patioPanel.classList.add('device-offline');
            addMessage(`🚨 **Alerta Extrema:** Hemos perdido conexión con el ESP32 en ${payload.ip}. Verificando perímetro a ciegas...`, 'system-alert');
        } else if (payload.event === 'reconnected') {
            patioPanel.classList.remove('device-offline');
            addMessage(`✅ **Conexión Recuperada:** El ESP32 en ${payload.ip} vuelve a estar en línea.`, 'assistant');
        }
    }

    initMqttStream();
    chatInput.focus();

    // =============================================
    //  PANEL DE CONFIGURACIÓN — TABBED
    // =============================================
    const btnSettings = document.getElementById('btn-settings');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettings = document.getElementById('close-settings');
    const btnDownload = document.getElementById('btn-download-code');
    const btnApply = document.getElementById('btn-apply-settings');
    const statusMsg = document.getElementById('settings-status');
    const CFG_KEY = 'yarvis_esp_config';

    // --- Tab switching ---
    document.querySelectorAll('.stab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.settings-tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            const target = document.getElementById(btn.dataset.tab);
            if (target) target.classList.add('active');
            if (btn.dataset.tab === 'tab-devices') loadDevicesFromDB();
        });
    });

    // --- Config persistence ---
    function loadConfig() {
        const saved = JSON.parse(localStorage.getItem(CFG_KEY) || '{}');
        if (saved.ssid) document.getElementById('cfg-wifi-ssid').value = saved.ssid;
        if (saved.pass) document.getElementById('cfg-wifi-pass').value = saved.pass;
        if (saved.brokerIp) document.getElementById('cfg-broker-ip').value = saved.brokerIp;
        if (saved.brokerPort) document.getElementById('cfg-broker-port').value = saved.brokerPort;
        if (saved.sirenPin) document.getElementById('cfg-siren-pin').value = saved.sirenPin;
    }

    function getConfig() {
        return {
            ssid: document.getElementById('cfg-wifi-ssid').value || 'TU_WIFI',
            pass: document.getElementById('cfg-wifi-pass').value || 'TU_PASSWORD',
            brokerIp: document.getElementById('cfg-broker-ip').value || '192.168.1.138',
            brokerPort: document.getElementById('cfg-broker-port').value || '1883',
            sirenPin: document.getElementById('cfg-siren-pin').value || '2',
        };
    }

    // --- Modal open/close ---
    btnSettings?.addEventListener('click', () => {
        loadConfig();
        settingsModal.classList.remove('hidden');
    });
    closeSettings?.addEventListener('click', () => settingsModal.classList.add('hidden'));
    settingsModal?.addEventListener('click', e => {
        if (e.target === settingsModal) settingsModal.classList.add('hidden');
    });

    // --- Save config ---
    btnApply?.addEventListener('click', () => {
        localStorage.setItem(CFG_KEY, JSON.stringify(getConfig()));
        showStatus('✅ Configuración guardada.', 'success', 'settings-status');
    });

    // --- Download Arduino code ---
    btnDownload?.addEventListener('click', async () => {
        const cfg = getConfig();
        localStorage.setItem(CFG_KEY, JSON.stringify(cfg));
        // Use first device IP if available
        const devices = await fetch('/api/devices').then(r => r.json()).catch(() => []);
        const espIp = devices.length ? devices[0].ip : '192.168.1.131';
        try {
            const resp = await fetch(`/api/esp/arduino?ip=${encodeURIComponent(espIp)}&broker_ip=${encodeURIComponent(cfg.brokerIp)}`);
            const data = await resp.json();
            if (data.arduino_code) {
                const code = data.arduino_code
                    .replace(/const char\* ssid\s*=\s*"[^"]*"/, `const char* ssid     = "${cfg.ssid}"`)
                    .replace(/const char\* password\s*=\s*"[^"]*"/, `const char* password = "${cfg.pass}"`)
                    .replace(/const int SIREN_LED_PIN = \d+/, `const int SIREN_LED_PIN = ${cfg.sirenPin}`);
                const blob = new Blob([code], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = 'yarvis_esp32_patio.ino'; a.click();
                URL.revokeObjectURL(url);
                showStatus('✅ Código descargado. Cárgalo en Arduino IDE.', 'success', 'settings-status');
            }
        } catch (e) {
            showStatus(`❌ Error: ${e.message}`, 'error', 'settings-status');
        }
    });

    // --- Add ESP (Tab 2) ---
    document.getElementById('btn-add-esp')?.addEventListener('click', async () => {
        const ip = document.getElementById('esp-ip-input')?.value.trim();
        const name = document.getElementById('esp-name-input')?.value.trim() || 'ESP32 Dispositivo';
        const type = document.getElementById('esp-type-select')?.value || 'esp32_security';
        if (!ip) { showStatus('⚠️ Ingresa una IP válida.', 'error', 'add-esp-status'); return; }

        showStatus('⏳ Conectando...', '', 'add-esp-status');
        try {
            const resp = await fetch('/api/esp/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip, name, dtype: type })
            });
            const data = await resp.json();
            if (data.status === 'success') {
                showStatus(`✅ ${data.device} vinculado en ${ip}.`, 'success', 'add-esp-status');
                if (data.state) updateSecurityUI(data.state);
                patioPanel?.classList.remove('hidden');
                startEspPolling(ip);
                setTimeout(() => {
                    document.querySelector('[data-tab="tab-devices"]')?.click();
                }, 800);
            } else {
                showStatus(`❌ ${data.message}`, 'error', 'add-esp-status');
            }
        } catch (e) {
            showStatus(`❌ Error: ${e.message}`, 'error', 'add-esp-status');
        }
    });

    // --- Download code for selected device type ---
    document.getElementById('btn-download-device-code')?.addEventListener('click', async () => {
        const type = document.getElementById('esp-type-select')?.value || 'esp32_security';
        const ip = document.getElementById('esp-ip-input')?.value.trim() || '192.168.1.131';
        const cfg = getConfig();

        let endpoint = `/api/esp/arduino?ip=${encodeURIComponent(ip)}&broker_ip=${encodeURIComponent(cfg.brokerIp)}`;
        let filename = 'yarvis_esp32_patio.ino';

        if (type === 'esp32_pool') {
            endpoint = `/api/esp/arduino/pool?ip=${encodeURIComponent(ip)}&broker_ip=${encodeURIComponent(cfg.brokerIp)}`;
            filename = 'yarvis_esp32_piscina.ino';
        } else if (type === 'esp32_kitchen') {
            endpoint = `/api/esp/arduino/kitchen?ip=${encodeURIComponent(ip)}&broker_ip=${encodeURIComponent(cfg.brokerIp)}`;
            filename = 'yarvis_esp32_cocina.ino';
        } else if (type === 'esp32_garden') {
            endpoint = `/api/esp/arduino/garden?ip=${encodeURIComponent(ip)}&broker_ip=${encodeURIComponent(cfg.brokerIp)}`;
            filename = 'yarvis_esp32_jardin.ino';
        }

        try {
            const data = await fetch(endpoint).then(r => r.json());
            if (data.arduino_code) {
                const code = data.arduino_code
                    .replace(/const char\* ssid\s*=\s*"[^"]*"/, `const char* ssid     = "${cfg.ssid}"`)
                    .replace(/const char\* password\s*=\s*"[^"]*"/, `const char* password = "${cfg.pass}"`);
                const blob = new Blob([code], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url; a.download = filename; a.click();
                URL.revokeObjectURL(url);
                showStatus(`✅ Código "${filename}" descargado.`, 'success', 'add-esp-status');
            }
        } catch (e) {
            showStatus(`❌ Error: ${e.message}`, 'error', 'add-esp-status');
        }
    });

    // ---- Device type definitions ----
    const DEVICE_DEFS = {
        esp32_security: {
            sensors: ['motion', 'motion_back', 'laser1', 'laser2', 'rf_access'],
            actuators: [
                { key: 'siren', label: '🚨 Sirena', on: 'on', off: 'off', field: 'accion' },
            ],
        },
        esp32_pool: {
            sensors: ['motion', 'agua'],
            actuators: [
                { key: 'luces_pis', label: '💡 Luces Piscina', on: 'on', off: 'off' },
                { key: 'luces_jac', label: '💡 Luces Jacuzzi', on: 'on', off: 'off' },
                { key: 'motor_jac', label: '⚙️ Motor Jacuzzi', on: 'on', off: 'off' },
                { key: 'motor_pis', label: '⚙️ Motor Piscina', on: 'on', off: 'off' },
            ],
        },
        esp32_kitchen: {
            sensors: ['motion', 'co', 'humo'],
            actuators: [
                { key: 'luces_cabinet', label: '💡 Luces Cabinet', on: 'on', off: 'off' },
                { key: 'luces_cocina', label: '💡 Luces Cocina', on: 'on', off: 'off' },
                { key: 'sirena', label: '🚨 Sirena Cocina', on: 'on', off: 'off' },
                { key: 'luces_isla', label: '💡 Luces Isla', on: 'on', off: 'off' },
                { key: 'luces_sala', label: '💡 Luces Sala', on: 'on', off: 'off' },
            ],
        },
        esp32_garden: {
            sensors: ['motion'],
            actuators: [
                { key: 'luces_izq', label: '💡 Luces Izq', on: 'on', off: 'off' },
                { key: 'luces_der', label: '💡 Luces Der', on: 'on', off: 'off' },
                { key: 'luces_frente', label: '💡 Luces Frente', on: 'on', off: 'off' },
                { key: 'luces_atras', label: '💡 Luces Atrás', on: 'on', off: 'off' },
                { key: 'motor_fuente', label: '⚙️ Motor Fuente', on: 'on', off: 'off' },
                { key: 'luces_fuente', label: '💡 Luces Fuente', on: 'on', off: 'off' },
                { key: 'luces_camino', label: '💡 Luces Camino', on: 'on', off: 'off' },
            ],
        },
    };

    // --- Devices Tab: Load from DB ---
    async function loadDevicesFromDB() {
        const listEl = document.getElementById('devices-db-list');
        if (!listEl) return;
        listEl.innerHTML = '<p class="empty-devices-msg">Cargando...</p>';
        try {
            const devices = await fetch('/api/devices').then(r => r.json());
            if (!devices.length) {
                listEl.innerHTML = '<p class="empty-devices-msg">No hay dispositivos guardados. Añade uno en la pestaña "Agregar ESP".</p>';
                return;
            }
            listEl.innerHTML = '';
            for (const dev of devices) {
                listEl.appendChild(buildDeviceCard(dev, listEl));
            }
        } catch (e) {
            listEl.innerHTML = `<p class="empty-devices-msg" style="color:#ef4444">Error: ${e.message}</p>`;
        }
    }

    function buildDeviceCard(dev, listEl) {
        const card = document.createElement('div');
        card.className = 'db-device-card';
        card.id = `db-card-${dev.ip.replace(/\./g, '-')}`;

        const dtype = dev.type || 'esp32_security';
        const def = DEVICE_DEFS[dtype] || DEVICE_DEFS.esp32_security;
        const state = dev.state || {};

        // --- Sensor badges (read-only) ---
        const sensorKeys = def.sensors;
        const sensorBadgesHTML = sensorKeys.map(k => {
            const v = state[k] || 'standby';
            const on = (v === 'active' || v === 'nivel_bajo');
            return `<span class="state-badge ${on ? 'badge-on' : ''}">${k}: ${v}</span>`;
        }).join('') || '<span style="color:#64748b;font-size:12px">Sin datos aún</span>';

        // --- Actuator buttons ---
        const actuatorBtnsHTML = def.actuators.map(a => {
            const v = state[a.key] || a.off;
            const isOn = v === a.on;
            return `<button class="actuator-btn ${isOn ? 'actuator-on' : ''}"
                        data-key="${a.key}" data-ip="${dev.ip}" data-dtype="${dtype}"
                        data-on="${a.on}" data-off="${a.off}">
                        ${a.label}
                    </button>`;
        }).join('');

        const typeLabel = dtype === 'esp32_pool' ? '🏊 Piscina'
            : dtype === 'esp32_kitchen' ? '🍳 Cocina'
                : dtype === 'esp32_garden' ? '🌿 Jardín'
                    : '🔒 Seguridad';

        card.innerHTML = `
            <div class="db-device-header">
                <div>
                    <strong>${dev.name}</strong>
                    <span class="db-device-ip">${dev.ip}</span>
                    <span class="db-device-type-badge">${typeLabel}</span>
                </div>
                <button class="btn-device-delete action-btn icon-only danger" data-ip="${dev.ip}" title="Eliminar">
                    <i class="ph ph-trash"></i>
                </button>
            </div>

            <div class="db-sensors-area">
                <div class="db-area-label">Sensores</div>
                <div class="db-device-states">${sensorBadgesHTML}</div>
            </div>

            <div class="db-actuators-area">
                <div class="db-area-label">Control</div>
                <div class="db-actuator-btns">${actuatorBtnsHTML}</div>
            </div>

            <div style="font-size:11px;color:#475569;margin-top:8px;">
                Añadido: ${new Date(dev.added_at).toLocaleString()}
            </div>
        `;

        // Delete
        card.querySelector('.btn-device-delete')?.addEventListener('click', async () => {
            if (!confirm(`¿Eliminar ${dev.name} (${dev.ip})?`)) return;
            await fetch(`/api/devices/${dev.ip}`, { method: 'DELETE' });
            card.remove();
            if (!listEl.children.length)
                listEl.innerHTML = '<p class="empty-devices-msg">Sin dispositivos guardados.</p>';
        });

        // Actuator toggle buttons
        card.querySelectorAll('.actuator-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const key = btn.dataset.key;
                const ip = btn.dataset.ip;
                const dtype = btn.dataset.dtype;
                const onVal = btn.dataset.on;
                const offVal = btn.dataset.off;
                const isOn = btn.classList.contains('actuator-on');
                const newVal = isOn ? offVal : onVal;

                btn.disabled = true;
                btn.style.opacity = '0.5';

                try {
                    const r = await fetch('/api/esp/control', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ip, dtype, command: { [key]: newVal } })
                    });
                    const d = await r.json();
                    if (d.status === 'ok') {
                        btn.classList.toggle('actuator-on', !isOn);
                    }
                } catch (e) {
                    console.error('Control error:', e);
                } finally {
                    btn.disabled = false;
                    btn.style.opacity = '1';
                }
            });
        });

        // Live polling
        startEspPollingForCard(dev.ip, card, def);
        return card;
    }


    function startEspPollingForCard(ip, card, def) {
        setInterval(async () => {
            try {
                const state = await fetch(`/api/esp/state?ip=${ip}`).then(r => r.json());
                if (state.error) return;

                // Update sensor badges
                const statesDiv = card.querySelector('.db-device-states');
                if (statesDiv && def) {
                    statesDiv.innerHTML = (def.sensors || []).map(k => {
                        const v = state[k] || 'standby';
                        const on = (v === 'active' || v === 'nivel_bajo');
                        return `<span class="state-badge ${on ? 'badge-on' : ''}">${k}: ${v}</span>`;
                    }).join('');
                }

                // Sync actuator button visual state
                card.querySelectorAll('.actuator-btn').forEach(btn => {
                    const key = btn.dataset.key;
                    const onVal = btn.dataset.on;
                    if (state[key] !== undefined) {
                        btn.classList.toggle('actuator-on', state[key] === onVal);
                    }
                });
            } catch { }
        }, 3000);
    }

    function showStatus(msg, type, elId = 'settings-status') {
        const el = document.getElementById(elId);
        if (!el) return;
        el.textContent = msg;
        el.className = `settings-status-msg ${type}`;
        el.classList.remove('hidden');
        setTimeout(() => el.classList.add('hidden'), 5000);
    }
});

