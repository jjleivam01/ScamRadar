// === YARVIS HYBRID NODE V2: VERSATILE CLOUD + EDGE ===
// Soporta JSON estructurado y matching de palabras clave flexible.

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ---- Credenciales WiFi ----
const char* ssid        = "Los Leiva";
const char* password    = "marmol123";

// ---- Configuración MQTT ----
const char* cloud_mqtt_server = "broker.hivemq.com";
const char* cloud_topic_cmd   = "john/yarvis/comandos";
const char* local_mqtt_server = "192.168.1.138"; 
const char* local_topic_state = "finca/cocina/estado";
const char* local_topic_cmd   = "finca/cocina/comando";
const char* global_topic_modo = "finca/sistema/modo";

// ---- Actuadores ----
const int PIN_LUCES_CAB = 26;
const int PIN_LUCES_COC = 27;
const int PIN_SIRENA    = 32;
const int PIN_LUCES_ISL = 33;
const int PIN_LUCES_SAL = 25;

WiFiClient espCloudClient, espLocalClient;
PubSubClient cloudMqtt(espCloudClient), localMqtt(espLocalClient);
WebServer server(80);

bool s_luces_cab = false, s_luces_coc = false, s_sirena = false, s_luces_isl = false, s_luces_sal = false;

void setRelay(int pin, bool on) { digitalWrite(pin, on ? LOW : HIGH); }

void applyHardware() {
  setRelay(PIN_LUCES_CAB, s_luces_cab);
  setRelay(PIN_LUCES_COC, s_luces_coc);
  setRelay(PIN_SIRENA,    s_sirena);
  setRelay(PIN_LUCES_ISL, s_luces_isl);
  setRelay(PIN_LUCES_SAL, s_luces_sal);
}

void publishLocalState() {
  DynamicJsonDocument doc(512);
  doc["luces_cabinet"] = s_luces_cab ? "on" : "off";
  doc["luces_cocina"]  = s_luces_coc ? "on" : "off";
  doc["sirena"]        = s_sirena    ? "on" : "off";
  doc["luces_isla"]    = s_luces_isl ? "on" : "off";
  doc["luces_sala"]    = s_luces_sal ? "on" : "off";
  char buf[512]; serializeJson(doc, buf);
  localMqtt.publish(local_topic_state, buf);
}

// Lógica de Matching Flexible
void processVersatileCommand(String action, String device) {
  action.toLowerCase(); device.toLowerCase();
  bool state = (action.indexOf("encend") != -1 || action.indexOf("prend") != -1 || action.indexOf("activ") != -1 || action.indexOf("pon") != -1);

  if (device.indexOf("sala") != -1 || device.indexOf("salon") != -1 || device.indexOf("estancia") != -1) s_luces_sal = state;
  if (device.indexOf("cocina") != -1 || device.indexOf("foco") != -1) s_luces_coc = state;
  if (device.indexOf("cabinet") != -1 || device.indexOf("gabinete") != -1) s_luces_cab = state;
  if (device.indexOf("isla") != -1 || device.indexOf("barra") != -1) s_luces_isl = state;
  if (device.indexOf("sirena") != -1 || device.indexOf("alarma") != -1) s_sirena = state;
  
  // Si dice "luces" o "todo", activar todo lo que sea luz
  if (device.indexOf("luces") != -1 || device.indexOf("todo") != -1) {
    s_luces_sal = s_luces_coc = s_luces_cab = s_luces_isl = state;
  }

  applyHardware();
  publishLocalState();
  Serial.printf("[Versatile] Acción: %s en %s\n", action.c_str(), device.c_str());
}

void cloudCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<512> doc;
  deserializeJson(doc, payload, length);
  
  if (doc.containsKey("action")) {
    String action = doc["action"].as<String>();
    if (action == "set_mode" && doc.containsKey("mode")) {
      StaticJsonDocument<128> modeDoc;
      modeDoc["mode"] = doc["mode"];
      String mStr; serializeJson(modeDoc, mStr);
      localCallback((char*)"finca/sistema/modo", (byte*)mStr.c_str(), mStr.length());
    } 
    else if (doc.containsKey("device")) {
      processVersatileCommand(action, doc["device"].as<String>());
    }
  }
}

void localCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<512> doc;
  deserializeJson(doc, payload, length);
  if (doc.containsKey("luces_sala"))    s_luces_sal = (doc["luces_sala"] == "on");
  if (doc.containsKey("luces_cocina"))  s_luces_coc = (doc["luces_cocina"] == "on");
  if (doc.containsKey("luces_isla"))    s_luces_isl = (doc["luces_isla"] == "on");
  if (doc.containsKey("luces_cabinet")) s_luces_cab = (doc["luces_cabinet"] == "on");
  if (doc.containsKey("sirena"))        s_sirena    = (doc["sirena"] == "on");
  
  // --- NUEVA LÓGICA DE MODOS GLOBALES ---
  if (doc.containsKey("mode")) {
    String m = doc["mode"].as<String>();
    Serial.printf("[ESP-Mode] Reaccionando a Modo: %s\n", m.c_str());
    
    if (m == "Manana") { s_luces_coc = true; s_luces_sal = true; s_luces_cab = false; }
    else if (m == "Dormir") { s_luces_coc = false; s_luces_sal = false; s_luces_cab = false; s_luces_isl = false; s_sirena = false; }
    else if (m == "Fiesta") { s_luces_coc = true; s_luces_sal = true; s_luces_isl = true; s_luces_cab = true; }
    else if (m == "Noche Romantica") { s_luces_isl = true; s_luces_cab = true; s_luces_coc = false; s_luces_sal = false; }
    else if (m == "Seguridad Maxima") { s_luces_coc = true; s_luces_sal = true; s_sirena = true; }
    else if (m == "Estudio") { s_luces_sal = true; s_luces_isl = true; }
  }

  applyHardware();
  publishLocalState();
}

void handleRestState() {
  DynamicJsonDocument doc(512);
  doc["luces_cabinet"] = s_luces_cab ? "on" : "off";
  doc["luces_cocina"]  = s_luces_coc ? "on" : "off";
  doc["sirena"]        = s_sirena    ? "on" : "off";
  doc["luces_isla"]    = s_luces_isl ? "on" : "off";
  doc["luces_sala"]    = s_luces_sal ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}

void reconnect() {
  if (!localMqtt.connected()) {
    if (localMqtt.connect("ESP32_Kitchen_Versatile")) {
      localMqtt.subscribe(local_topic_cmd);
      localMqtt.subscribe(global_topic_modo);
      publishLocalState();
    }
  }
  if (!cloudMqtt.connected()) {
    String cid = "AlexaVersatile-" + String(random(0xFFFF), HEX);
    if (cloudMqtt.connect(cid.c_str())) {
      cloudMqtt.subscribe(cloud_topic_cmd);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LUCES_CAB, OUTPUT); pinMode(PIN_LUCES_COC, OUTPUT);
  pinMode(PIN_SIRENA, OUTPUT); pinMode(PIN_LUCES_ISL, OUTPUT); pinMode(PIN_LUCES_SAL, OUTPUT);
  applyHardware(); 

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  
  cloudMqtt.setServer(cloud_mqtt_server, 1883); cloudMqtt.setCallback(cloudCallback);
  localMqtt.setServer(local_mqtt_server, 1883); localMqtt.setCallback(localCallback);
  server.on("/state", handleRestState); server.begin();
}

void loop() {
  if (!cloudMqtt.connected() || !localMqtt.connected()) reconnect();
  cloudMqtt.loop(); localMqtt.loop(); server.handleClient();
  delay(10);
}
