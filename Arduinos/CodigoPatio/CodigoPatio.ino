// Generado por Yarvis Edge Command Center
// Teclas en Serial Monitor:
//   1 = Mov. Frontal   2 = Mov. Trasero
//   3 = Laser 1        4 = Laser 2
//   5 = Acceso RF      6 = Sirena ON/OFF
#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>
const char* ssid        = "Los Leiva";
const char* password    = "marmol123";
const char* mqtt_server = "192.168.1.138"; // IP de tu PC
const int SIREN_LED_PIN = 2;
WiFiClient espClient;
PubSubClient mqtt(espClient);
WebServer server(80);
bool s_motion_front = false;
bool s_motion_back  = false;
bool s_laser1       = false;
bool s_laser2       = false;
bool s_rf_access    = false;
bool s_siren        = false;
void setup_wifi() {
  Serial.print("Conectando a WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.print("\nWiFi conectado. IP: ");
  Serial.println(WiFi.localIP());
}
void publishState() {
  DynamicJsonDocument doc(512);
  doc["motion"]      = s_motion_front ? "active" : "standby";
  doc["motion_back"] = s_motion_back  ? "active" : "standby";
  doc["laser1"]      = s_laser1       ? "active" : "standby";
  doc["laser2"]      = s_laser2       ? "active" : "standby";
  doc["rf_access"]   = s_rf_access    ? "active" : "standby";
  doc["siren"]       = s_siren        ? "active" : "standby";
  char buffer[512];
  serializeJson(doc, buffer);
  mqtt.publish("finca/seguridad/patio/estado", buffer);
  Serial.print("[MQTT] -> "); Serial.println(buffer);
}
void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  if (String(topic) == "finca/seguridad/patio/siren/comando") {
    DynamicJsonDocument doc(256);
    deserializeJson(doc, msg);
    s_siren = (String(doc["accion"].as<const char*>()) == "on");
    digitalWrite(SIREN_LED_PIN, s_siren ? HIGH : LOW);
    Serial.println(s_siren ? "SIRENA ACTIVADA" : "SIRENA DESACTIVADA");
    publishState();
  }
}
void reconnect() {
  while (!mqtt.connected()) {
    Serial.print("Intentando conexión MQTT...");
    if (mqtt.connect("ESP32_Patio_Client")) {
      Serial.println("conectado");
      mqtt.subscribe("finca/seguridad/patio/siren/comando");
      publishState();
    } else {
      Serial.print("falló, rc="); Serial.println(mqtt.state());
      delay(3000);
    }
  }
}
void handleState() {
  DynamicJsonDocument doc(512);
  doc["motion"]      = s_motion_front ? "active" : "standby";
  doc["motion_back"] = s_motion_back  ? "active" : "standby";
  doc["laser1"]      = s_laser1       ? "active" : "standby";
  doc["laser2"]      = s_laser2       ? "active" : "standby";
  doc["rf_access"]   = s_rf_access    ? "active" : "standby";
  doc["siren"]       = s_siren        ? "active" : "standby";
  String r; serializeJson(doc, r);
  server.send(200, "application/json", r);
}
void handlePing() { server.send(200, "text/plain", "pong"); }
void handleSerialInput(char key) {
  switch (key) {
    case '1': s_motion_front = !s_motion_front;
              Serial.println(s_motion_front ? "[1] Mov. Frontal: ACTIVO" : "[1] Mov. Frontal: INACTIVO"); break;
    case '2': s_motion_back = !s_motion_back;
              Serial.println(s_motion_back ? "[2] Mov. Trasero: ACTIVO" : "[2] Mov. Trasero: INACTIVO"); break;
    case '3': s_laser1 = !s_laser1;
              Serial.println(s_laser1 ? "[3] Laser 1: ACTIVO" : "[3] Laser 1: INACTIVO"); break;
    case '4': s_laser2 = !s_laser2;
              Serial.println(s_laser2 ? "[4] Laser 2: ACTIVO" : "[4] Laser 2: INACTIVO"); break;
    case '5': s_rf_access = !s_rf_access;
              Serial.println(s_rf_access ? "[5] Acceso RF: ACTIVO" : "[5] Acceso RF: INACTIVO"); break;
    case '6': s_siren = !s_siren;
              digitalWrite(SIREN_LED_PIN, s_siren ? HIGH : LOW);
              Serial.println(s_siren ? "[6] Sirena: ACTIVO" : "[6] Sirena: INACTIVO"); break;
    default:
      Serial.println("Teclas: 1=MvFront 2=MvBack 3=Laser1 4=Laser2 5=RF 6=Sirena");
      return;
  }
  publishState();
}
void setup() {
  Serial.begin(115200);
  pinMode(SIREN_LED_PIN, OUTPUT);
  digitalWrite(SIREN_LED_PIN, LOW);
  setup_wifi();
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);
  server.on("/state", handleState);
  server.on("/ping", handlePing);
  server.begin();
  Serial.println("\n=== YARVIS ESP32 LISTO ===");
  Serial.println("Teclas: 1=MvFront 2=MvBack 3=Laser1 4=Laser2 5=RF 6=Sirena");
}
void loop() {
  if (!mqtt.connected()) reconnect();
  mqtt.loop();
  server.handleClient();
  if (Serial.available() > 0) {
    char key = Serial.read();
    handleSerialInput(key);
  }
  delay(50);
}