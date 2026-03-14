// === YARVIS POOL CONTROLLER ESP32 ===
// Generado por Yarvis Edge Command Center
//
// SENSORES:
//   PIN 14 = PIR Movimiento
//   PIN 35 = Nivel de Agua (HIGH = nivel bajo = necesita recarga)
//
// ACTUADORES (RELÉS - activo en LOW):
//   PIN 26 = Luces Fondo Piscina
//   PIN 27 = Luces Jacuzzi
//   PIN 32 = Motor Jacuzzi
//   PIN 33 = Motor Piscina
//
// TECLAS SERIAL MONITOR:
//   1 = Sensor Movimiento ON/OFF
//   2 = Nivel Agua NORMAL/BAJO
//   3 = Luces Piscina ON/OFF
//   4 = Luces Jacuzzi ON/OFF
//   5 = Motor Jacuzzi ON/OFF
//   6 = Motor Piscina ON/OFF
//   0 = APAGAR TODO (emergencia)

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

const char* ssid        = "Los Leiva";        // <-- Cambia esto
const char* password    = "marmol123";    // <-- Cambia esto
const char* mqtt_server = "192.168.1.138";  // <-- IP de tu PC con Mosquitto

// ---- Pines ----
const int PIR_PIN       = 14;
const int WATER_PIN     = 35;  // HIGH = nivel bajo
const int PIN_LUCES_PIS = 26;
const int PIN_LUCES_JAC = 27;
const int PIN_MOTOR_JAC = 32;
const int PIN_MOTOR_PIS = 33;

// ---- Topics MQTT ----
const char* TOPIC_ESTADO  = "finca/piscina/estado";
const char* TOPIC_COMANDO = "finca/piscina/comando";

WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);

// ---- Estados ----
bool s_motion    = false;
bool s_water_low = false;
bool s_luces_pis = false;
bool s_luces_jac = false;
bool s_motor_jac = false;
bool s_motor_pis = false;

void setRelay(int pin, bool on) {
  digitalWrite(pin, on ? LOW : HIGH);  // LOW = ON en modulos de rele
}

void applyActuators() {
  setRelay(PIN_LUCES_PIS, s_luces_pis);
  setRelay(PIN_LUCES_JAC, s_luces_jac);
  setRelay(PIN_MOTOR_JAC, s_motor_jac);
  setRelay(PIN_MOTOR_PIS, s_motor_pis);
}

void publishState() {
  DynamicJsonDocument doc(512);
  doc["motion"]    = s_motion    ? "active"     : "standby";
  doc["agua"]      = s_water_low ? "nivel_bajo" : "normal";
  doc["luces_pis"] = s_luces_pis ? "on" : "off";
  doc["luces_jac"] = s_luces_jac ? "on" : "off";
  doc["motor_jac"] = s_motor_jac ? "on" : "off";
  doc["motor_pis"] = s_motor_pis ? "on" : "off";
  char buf[512];
  serializeJson(doc, buf);
  mqtt.publish(TOPIC_ESTADO, buf);
  Serial.print("[MQTT] -> "); Serial.println(buf);
}

void emergencyOff() {
  s_luces_pis = s_luces_jac = s_motor_jac = s_motor_pis = false;
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

  if (doc.containsKey("luces_pis")) s_luces_pis = (String(doc["luces_pis"].as<const char*>()) == "on");
  if (doc.containsKey("luces_jac")) s_luces_jac = (String(doc["luces_jac"].as<const char*>()) == "on");
  if (doc.containsKey("motor_jac")) s_motor_jac = (String(doc["motor_jac"].as<const char*>()) == "on");
  if (doc.containsKey("motor_pis")) s_motor_pis = (String(doc["motor_pis"].as<const char*>()) == "on");
  if (doc.containsKey("apagar_todo") && doc["apagar_todo"].as<bool>()) { emergencyOff(); return; }

  applyActuators();
  publishState();
}

void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("Conectando MQTT...");
    if (mqtt.connect("ESP32_Pool_Client")) {
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
  doc["motion"]    = s_motion    ? "active"     : "standby";
  doc["agua"]      = s_water_low ? "nivel_bajo" : "normal";
  doc["luces_pis"] = s_luces_pis ? "on" : "off";
  doc["luces_jac"] = s_luces_jac ? "on" : "off";
  doc["motor_jac"] = s_motor_jac ? "on" : "off";
  doc["motor_pis"] = s_motor_pis ? "on" : "off";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}

void handlePing() { server.send(200, "text/plain", "pong"); }

void handleSerialInput(char key) {
  switch (key) {
    case '1': s_motion    = !s_motion;
              Serial.println(s_motion    ? "[1] Movimiento: ACTIVO"    : "[1] Movimiento: INACTIVO"); break;
    case '2': s_water_low = !s_water_low;
              Serial.println(s_water_low ? "[2] Agua: NIVEL BAJO"      : "[2] Agua: NORMAL"); break;
    case '3': s_luces_pis = !s_luces_pis;
              Serial.println(s_luces_pis ? "[3] Luces Piscina: ON"     : "[3] Luces Piscina: OFF"); break;
    case '4': s_luces_jac = !s_luces_jac;
              Serial.println(s_luces_jac ? "[4] Luces Jacuzzi: ON"     : "[4] Luces Jacuzzi: OFF"); break;
    case '5': s_motor_jac = !s_motor_jac;
              Serial.println(s_motor_jac ? "[5] Motor Jacuzzi: ON"     : "[5] Motor Jacuzzi: OFF"); break;
    case '6': s_motor_pis = !s_motor_pis;
              Serial.println(s_motor_pis ? "[6] Motor Piscina: ON"     : "[6] Motor Piscina: OFF"); break;
    case '0': emergencyOff(); return;
    default:
      Serial.println("Teclas: 1=Mov 2=Agua 3=LucesPis 4=LucesJac 5=MotorJac 6=MotorPis 0=APAGAR");
      return;
  }
  applyActuators();
  publishState();
}

bool last_pir   = false;
bool last_water = false;

void setup() {
  Serial.begin(115200);

  // Sensores
  pinMode(PIR_PIN,   INPUT);
  pinMode(WATER_PIN, INPUT);

  // Actuadores — relés APAGADOS al iniciar (HIGH)
  pinMode(PIN_LUCES_PIS, OUTPUT); digitalWrite(PIN_LUCES_PIS, HIGH);
  pinMode(PIN_LUCES_JAC, OUTPUT); digitalWrite(PIN_LUCES_JAC, HIGH);
  pinMode(PIN_MOTOR_JAC, OUTPUT); digitalWrite(PIN_MOTOR_JAC, HIGH);
  pinMode(PIN_MOTOR_PIS, OUTPUT); digitalWrite(PIN_MOTOR_PIS, HIGH);

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

  Serial.println("\n=== YARVIS POOL CONTROLLER LISTO ===");
  Serial.println("Teclas: 1=Mov 2=Agua 3=LucesPis 4=LucesJac 5=MotorJac 6=MotorPis 0=APAGAR");
}

void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();

  // Leer sensores físicos — publicar solo si cambian
  bool pir   = digitalRead(PIR_PIN)   == HIGH;
  bool water = digitalRead(WATER_PIN) == HIGH;
  if (pir != last_pir || water != last_water) {
    s_motion    = pir;
    s_water_low = water;
    last_pir    = pir;
    last_water  = water;
    publishState();
    if (s_water_low) Serial.println("[!] ALERTA: Nivel de agua bajo");
  }

  // Testing por Serial Monitor
  if (Serial.available() > 0) {
    handleSerialInput(Serial.read());
  }

  delay(50);
}
