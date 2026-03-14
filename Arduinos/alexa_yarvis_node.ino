// === YARVIS HYBRID NODE: ALEXA CLOUD + EDGE LOCAL ===
// Este código permite que el ESP32 responda a Alexa (Nube) y a Yarvis (Local) simultáneamente.
//

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ---- Credenciales WiFi ----
const char* ssid        = "Los Leiva";
const char* password    = "marmol123";

// ---- Configuración Nube (Alexa via HiveMQ) ----
const char* cloud_mqtt_server = "broker.hivemq.com";
const char* cloud_topic_cmd   = "john/yarvis/comandos";

// ---- Configuración Local (Yarvis Edge) ----
const char* local_mqtt_server = "192.168.1.138"; // <-- Ajusta a la IP de tu PC/Servidor
const char* local_topic_state = "finca/cocina/estado";
const char* local_topic_cmd   = "finca/cocina/comando";

// ---- Pines Actuadores ----
const int PIN_LUCES_CAB = 26;
const int PIN_LUCES_COC = 27;
const int PIN_SIRENA    = 32;
const int PIN_LUCES_ISL = 33;
const int PIN_LUCES_SAL = 25;

// ---- Clientes ----
WiFiClient espCloudClient;
PubSubClient cloudMqtt(espCloudClient);

WiFiClient espLocalClient;
PubSubClient localMqtt(espLocalClient);

WebServer server(80);

// ---- Estado del Hardware ----
bool s_luces_cab = false;
bool s_luces_coc = false;
bool s_sirena    = false;
bool s_luces_isl = false;
bool s_luces_sal = false;

void setRelay(int pin, bool on) {
  digitalWrite(pin, on ? LOW : HIGH);
}

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
  
  char buf[512];
  serializeJson(doc, buf);
  localMqtt.publish(local_topic_state, buf);
  Serial.println("[Local MQTT] Estado reportado a Yarvis.");
}

// Handler para Comandos de Alexa (Nube)
void cloudCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  
  Serial.print("[ALEXA CLOUD] -> "); Serial.println(msg);

  int sep = msg.indexOf(':');
  if (sep == -1) return;

  String action = msg.substring(0, sep);
  String device = msg.substring(sep + 1);
  action.toLowerCase(); device.toLowerCase();

  bool state = (action == "enciende" || action == "activa" || action == "prende");

  if (device == "cabinet") s_luces_cab = state;
  else if (device == "cocina")  s_luces_coc = state;
  else if (device == "sirena")  s_sirena    = state;
  else if (device == "isla")    s_luces_isl = state;
  else if (device == "sala")    s_luces_sal = state;
  
  applyHardware();
  publishLocalState(); // Sincroniza con el Dashboard local
}

// Handler para Comandos de Yarvis (Local)
void localCallback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  
  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, msg) != DeserializationError::Ok) return;

  if (doc.containsKey("luces_cabinet")) s_luces_cab = (doc["luces_cabinet"] == "on");
  if (doc.containsKey("luces_cocina"))  s_luces_coc = (doc["luces_cocina"]  == "on");
  if (doc.containsKey("sirena"))        s_sirena    = (doc["sirena"]        == "on");
  if (doc.containsKey("luces_isla"))    s_luces_isl = (doc["luces_isla"]    == "on");
  if (doc.containsKey("luces_sala"))    s_luces_sal = (doc["luces_sala"]    == "on");

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
  // Reifis Local Yarvis
  if (!localMqtt.connected()) {
    Serial.print("Conectando Local Yarvis...");
    if (localMqtt.connect("ESP32_Kitchen_Local")) {
      Serial.println("OK");
      localMqtt.subscribe(local_topic_cmd);
      publishLocalState();
    }
  }
  // Reifis Cloud Alexa
  if (!cloudMqtt.connected()) {
    Serial.print("Conectando Alexa Cloud...");
    String cid = "AlexaNode-" + String(random(0xFFFF), HEX);
    if (cloudMqtt.connect(cid.c_str())) {
      Serial.println("OK");
      cloudMqtt.subscribe(cloud_topic_cmd);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LUCES_CAB, OUTPUT); digitalWrite(PIN_LUCES_CAB, HIGH);
  pinMode(PIN_LUCES_COC, OUTPUT); digitalWrite(PIN_LUCES_COC, HIGH);
  pinMode(PIN_SIRENA,    OUTPUT); digitalWrite(PIN_SIRENA,    HIGH);
  pinMode(PIN_LUCES_ISL, OUTPUT); digitalWrite(PIN_LUCES_ISL, HIGH);
  pinMode(PIN_LUCES_SAL, OUTPUT); digitalWrite(PIN_LUCES_SAL, HIGH);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nIP: " + WiFi.localIP().toString());

  cloudMqtt.setServer(cloud_mqtt_server, 1883);
  cloudMqtt.setCallback(cloudCallback);

  localMqtt.setServer(local_mqtt_server, 1883);
  localMqtt.setCallback(localCallback);

  server.on("/state", handleRestState);
  server.begin();
}

void loop() {
  if (!cloudMqtt.connected() || !localMqtt.connected()) reconnect();
  cloudMqtt.loop();
  localMqtt.loop();
  server.handleClient();
  delay(10);
}
