#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <cstring>

#include "config.h"

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastPublishAt = 0;

String telemetryTopic() {
  return String("aiot/room/") + AIOT_ROOM_ID + "/telemetry";
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.printf("Connecting Wi-Fi SSID=%s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\nWi-Fi connected, ip=%s\n", WiFi.localIP().toString().c_str());
}

void connectMqtt() {
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqttClient.connected()) {
    Serial.printf("Connecting MQTT %s:%d\n", MQTT_HOST, MQTT_PORT);
    bool ok = false;
    if (strlen(MQTT_USERNAME) > 0) {
      ok = mqttClient.connect(AIOT_DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD);
    } else {
      ok = mqttClient.connect(AIOT_DEVICE_ID);
    }
    if (!ok) {
      Serial.printf("MQTT connect failed, state=%d\n", mqttClient.state());
      delay(3000);
    }
  }
}

float readTemperatureC() {
  return 25.0f;
}

float readHumidityPct() {
  return 48.0f;
}

float readCo2Ppm() {
  const int raw = analogRead(AIOT_CO2_ADC_PIN);
  return 500.0f + (static_cast<float>(raw) / 4095.0f) * 1200.0f;
}

float readLightLux() {
  const int raw = analogRead(AIOT_LIGHT_ADC_PIN);
  return (static_cast<float>(raw) / 4095.0f) * 1000.0f;
}

float readPresence() {
  return digitalRead(AIOT_PRESENCE_PIN) == HIGH ? 1.0f : 0.0f;
}

float readNoiseDbA() {
  const int raw = analogRead(AIOT_NOISE_ADC_PIN);
  return 32.0f + (static_cast<float>(raw) / 4095.0f) * 55.0f;
}

void addReading(JsonArray readings, const char *metric, float value, const char *unit, const char *quality = "ok") {
  JsonObject reading = readings.add<JsonObject>();
  reading["metric"] = metric;
  reading["value"] = value;
  reading["unit"] = unit;
  reading["quality"] = quality;
}

bool publishTelemetry() {
  StaticJsonDocument<1024> payload;
  payload["device_id"] = AIOT_DEVICE_ID;
  JsonArray readings = payload["readings"].to<JsonArray>();

  addReading(readings, "temperature", readTemperatureC(), "\xE2\x84\x83");
  addReading(readings, "humidity", readHumidityPct(), "%");

  const float co2 = readCo2Ppm();
  addReading(readings, "co2", co2, "ppm", co2 > 1200.0f ? "anomaly" : "ok");
  addReading(readings, "light", readLightLux(), "lux");
  addReading(readings, "presence", readPresence(), "occupied");
  const float noise = readNoiseDbA();
  addReading(readings, "noise", noise, "dB", noise > 65.0f ? "anomaly" : "ok");

  char buffer[1024];
  const size_t size = serializeJson(payload, buffer, sizeof(buffer));
  const String topic = telemetryTopic();
  const bool ok = mqttClient.publish(topic.c_str(), reinterpret_cast<const uint8_t *>(buffer), size, false);
  Serial.printf("publish topic=%s bytes=%u ok=%s\n", topic.c_str(), static_cast<unsigned>(size), ok ? "true" : "false");
  return ok;
}

void setup() {
  Serial.begin(115200);
  pinMode(AIOT_PRESENCE_PIN, INPUT);
  analogReadResolution(12);
  connectWifi();
  connectMqtt();
}

void loop() {
  connectWifi();
  connectMqtt();
  mqttClient.loop();

  const unsigned long nowMs = millis();
  if (nowMs - lastPublishAt >= AIOT_SAMPLE_INTERVAL_MS || lastPublishAt == 0) {
    publishTelemetry();
    lastPublishAt = nowMs;
  }
}
