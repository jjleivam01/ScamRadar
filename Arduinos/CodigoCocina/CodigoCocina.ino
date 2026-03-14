// === YARVIS KITCHEN CONTROLLER ESP32 ===
// Generado por Yarvis Edge Command Center
//
// SENSORES:
//   PIN 14  = PIR Movimiento
//   PIN 34  = MQ-7 Monóxido de Carbono (analógico, >1800 = alerta)
//   PIN 35  = MQ-2 Humo (digital, LOW = humo detectado)
//
// ACTUADORES (RELÉS - activo en LOW):
//   PIN 26  = Luces Cabinet
//   PIN 27  = Luces Cocina
//   PIN 32  = Sirena Cocina
//   PIN 33  = Luces Isla
//   PIN 25  = Luces Sala
//
// TECLAS SERIAL MONITOR:
//   1=Movimiento  2=CO  3=Humo
//   4=Cabinet  5=Cocina  6=Sirena  7=Isla  8=Sala
//   0=APAGAR TODO

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid        = "Los Leiva";        // <-- Cambia esto
const char* password    = "marmol123";    // <-- Cambia esto
const char* mqtt_server = "192.168.1.138";  // <-- IP de tu PC

// ---- Pines Sensores ----
const int PIR_PIN   = 14;
const int CO_PIN    = 34;  // Analógico
const int SMOKE_PIN = 35;  // Digital: LOW = humo

// ---- Pines Actuadores (Relés) ----
const int PIN_LUCES_CAB = 26;
const int PIN_LUCES_COC = 27;
const int PIN_SIRENA    = 32;
const int PIN_LUCES_ISL = 33;
const int PIN_LUCES_SAL = 25;

// ---- Umbral CO ----
const int CO_THRESHOLD = 1800;  // ADC > umbral = peligro

// ---- Topics MQTT ----
const char* TOPIC_ESTADO  = "finca/cocina/estado";
const char* TOPIC_COMANDO = "finca/cocina/comando";

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// ---- Estados ----
bool s_motion    = false;
bool s_co_alert  = false;
bool s_humo      = false;
bool s_luces_cab = false;
bool s_luces_coc = false;
bool s_sirena    = false;
bool s_luces_isl = false;
bool s_luces_sal = false;

void setRelay(int pin, bool on) {
  digitalWrite(pin, on ? LOW : HIGH);
}

void applyActuators() {
  setRelay(PIN_LUCES_CAB, s_luces_cab);
  setRelay(PIN_LUCES_COC, s_luces_coc);
  setRelay(PIN_SIRENA,    s_sirena);
  setRelay(PIN_LUCES_ISL, s_luces_isl);
  setRelay(PIN_LUCES_SAL, s_luces_sal);
}

void publishState() {
  DynamicJsonDocument doc(512);
  doc["motion"]        = s_motion    ? "active"    : "standby";
  doc["co"]            = s_co_alert  ? "alerta"    : "normal";
  doc["humo"]          = s_humo      ? "detectado" : "normal";
  doc["luces_cabinet"] = s_luces_cab ? "on" : "off";
  doc["luces_cocina"]  = s_luces_coc ? "on" : "off";
  doc["sirena"]        = s_sirena    ? "on" : "off";
  doc["luces_isla"]    = s_luces_isl ? "on" : "off";
  doc["luces_sala"]    = s_luces_sal ? "on" : "off";
  char buf[512];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ESTADO, buf);
  Serial.print("[MQTT] -> "); Serial.println(buf);
}

void emergencyOff() {
  s_luces_cab = s_luces_coc = s_sirena = s_luces_isl = s_luces_sal = false;
  applyActuators();
  Serial.println("[!] APAGADO DE EMERGENCIA");
  publishState();
}

void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  Serial.print("[MQTT CMD] "); Serial.println(msg);

  DynamicJsonDocument doc(512);
  if (deserializeJson(doc, msg) != DeserializationError::Ok) return;

  if (doc.containsKey("luces_cabinet")) s_luces_cab = (String(doc["luces_cabinet"].as<const char*>()) == "on");
  if (doc.containsKey("luces_cocina"))  s_luces_coc = (String(doc["luces_cocina"].as<const char*>())  == "on");
  if (doc.containsKey("sirena"))        s_sirena    = (String(doc["sirena"].as<const char*>())         == "on");
  if (doc.containsKey("luces_isla"))    s_luces_isl = (String(doc["luces_isla"].as<const char*>())    == "on");
  if (doc.containsKey("luces_sala"))    s_luces_sal = (String(doc["luces_sala"].as<const char*>())    == "on");
  if (doc.containsKey("apagar_todo") && doc["apagar_todo"].as<bool>()) { emergencyOff(); return; }

  applyActuators();
  publishState();
}

void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("Conectando MQTT...");
    if (mqtt.connect("ESP32_Kitchen_Client")) {
      Serial.println("OK");
      mqtt.subscribe(TOPIC_COMANDO);
      publishState();
    } else {
      Serial.print("Error rc="); Serial.println(mqtt.state());
      delay(3000);
    }
  }
}

void handleState() {
  DynamicJsonDocument doc(512);
  doc["motion"]        = s_motion    ? "active"    : "standby";
  doc["co"]            = s_co_alert  ? "alerta"    : "normal";
  doc["humo"]          = s_humo      ? "detectado" : "normal";
  doc["luces_cabinet"] = s_luces_cab ? "on" : "off";
  doc["luces_cocina"]  = s_luces_coc ? "on" : "off";
  doc["sirena"]        = s_sirena    ? "on" : "off";
  doc["luces_isla"]    = s_luces_isl ? "on" : "off";
  doc["luces_sala"]    = s_luces_sal ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}

void handlePing() { server.send(200, "text/plain", "pong"); }

void handleSerialInput(char key) {
  switch (key) {
    case '1': s_motion    = !s_motion;
              Serial.println(s_motion    ? "[1] Movimiento: ACTIVO"   : "[1] Movimiento: INACTIVO"); break;
    case '2': s_co_alert  = !s_co_alert;
              Serial.println(s_co_alert  ? "[2] CO: ALERTA"           : "[2] CO: NORMAL"); break;
    case '3': s_humo      = !s_humo;
              Serial.println(s_humo      ? "[3] Humo: DETECTADO"      : "[3] Humo: NORMAL"); break;
    case '4': s_luces_cab = !s_luces_cab;
              Serial.println(s_luces_cab ? "[4] Luces Cabinet: ON"    : "[4] Luces Cabinet: OFF"); break;
    case '5': s_luces_coc = !s_luces_coc;
              Serial.println(s_luces_coc ? "[5] Luces Cocina: ON"     : "[5] Luces Cocina: OFF"); break;
    case '6': s_sirena    = !s_sirena;
              Serial.println(s_sirena    ? "[6] Sirena: ON"           : "[6] Sirena: OFF"); break;
    case '7': s_luces_isl = !s_luces_isl;
              Serial.println(s_luces_isl ? "[7] Luces Isla: ON"       : "[7] Luces Isla: OFF"); break;
    case '8': s_luces_sal = !s_luces_sal;
              Serial.println(s_luces_sal ? "[8] Luces Sala: ON"       : "[8] Luces Sala: OFF"); break;
    case '0': emergencyOff(); return;
    default:
      Serial.println("Teclas: 1=Mov 2=CO 3=Humo 4=Cabinet 5=Cocina 6=Sirena 7=Isla 8=Sala 0=APAGAR");
      return;
  }
  applyActuators();
  publishState();
}

bool last_pir  = false;
bool last_co   = false;
bool last_humo = false;

void setup() {
  Serial.begin(115200);

  // Sensores
  pinMode(PIR_PIN,   INPUT);
  pinMode(SMOKE_PIN, INPUT_PULLUP);  // LOW = humo

  // Actuadores — relés APAGADOS al iniciar (HIGH)
  pinMode(PIN_LUCES_CAB, OUTPUT); digitalWrite(PIN_LUCES_CAB, HIGH);
  pinMode(PIN_LUCES_COC, OUTPUT); digitalWrite(PIN_LUCES_COC, HIGH);
  pinMode(PIN_SIRENA,    OUTPUT); digitalWrite(PIN_SIRENA,    HIGH);
  pinMode(PIN_LUCES_ISL, OUTPUT); digitalWrite(PIN_LUCES_ISL, HIGH);
  pinMode(PIN_LUCES_SAL, OUTPUT); digitalWrite(PIN_LUCES_SAL, HIGH);

  // WiFi
  Serial.print("WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.print(" IP: "); Serial.println(WiFi.localIP());

  // MQTT
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);

  // HTTP endpoints
  server.on("/state", handleState);
  server.on("/ping",  handlePing);
  server.begin();

  Serial.println("\n=== YARVIS KITCHEN CONTROLLER LISTO ===");
  Serial.println("Teclas: 1=Mov 2=CO 3=Humo 4=Cabinet 5=Cocina 6=Sirena 7=Isla 8=Sala 0=APAGAR");
}

void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Sensores físicos — publicar solo si cambian
  bool pir  = digitalRead(PIR_PIN) == HIGH;
  int  co   = analogRead(CO_PIN);
  bool humo = digitalRead(SMOKE_PIN) == LOW;  // LOW = humo detectado

  bool co_alert = (co > CO_THRESHOLD);

  if (pir != last_pir || co_alert != last_co || humo != last_humo) {
    s_motion   = pir;
    s_co_alert = co_alert;
    s_humo     = humo;
    last_pir   = pir;
    last_co    = co_alert;
    last_humo  = humo;
    publishState();
    if (co_alert) Serial.printf("[!] ALERTA CO: ADC=%d\n", co);
    if (humo)     Serial.println("[!] ALERTA HUMO DETECTADO");
  }

  // Testing por Serial Monitor
  if (Serial.available() > 0) {
    handleSerialInput(Serial.read());
  }

  delay(50);
}
