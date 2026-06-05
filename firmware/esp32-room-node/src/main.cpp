#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <cstring>
#include <cmath>
#include <Wire.h>

#include "config.h"

#ifndef AIOT_I2C_SDA_PIN
#define AIOT_I2C_SDA_PIN SDA
#endif

#ifndef AIOT_I2C_SCL_PIN
#define AIOT_I2C_SCL_PIN SCL
#endif

#ifndef AIOT_USE_SHT31
#define AIOT_USE_SHT31 0
#endif

#ifndef AIOT_SHT31_ADDRESS
#define AIOT_SHT31_ADDRESS 0x44
#endif

#ifndef AIOT_USE_BH1750
#define AIOT_USE_BH1750 0
#endif

#ifndef AIOT_BH1750_ADDRESS
#define AIOT_BH1750_ADDRESS 0x23
#endif

#ifndef AIOT_USE_SCD4X
#define AIOT_USE_SCD4X 0
#endif

#ifndef AIOT_SCD4X_ADDRESS
#define AIOT_SCD4X_ADDRESS 0x62
#endif

#ifndef AIOT_USE_ANALOG_CO2
#define AIOT_USE_ANALOG_CO2 0
#endif

#ifndef AIOT_USE_ANALOG_LIGHT
#define AIOT_USE_ANALOG_LIGHT 0
#endif

#ifndef AIOT_USE_ANALOG_NOISE
#define AIOT_USE_ANALOG_NOISE 0
#endif

#ifndef AIOT_ANALOG_CO2_MIN_PPM
#define AIOT_ANALOG_CO2_MIN_PPM 400.0f
#endif

#ifndef AIOT_ANALOG_CO2_MAX_PPM
#define AIOT_ANALOG_CO2_MAX_PPM 2000.0f
#endif

#ifndef AIOT_ANALOG_LIGHT_MAX_LUX
#define AIOT_ANALOG_LIGHT_MAX_LUX 1200.0f
#endif

#ifndef AIOT_ANALOG_NOISE_MIN_DB
#define AIOT_ANALOG_NOISE_MIN_DB 32.0f
#endif

#ifndef AIOT_ANALOG_NOISE_MAX_DB
#define AIOT_ANALOG_NOISE_MAX_DB 88.0f
#endif

#ifndef AIOT_ALLOW_DEMO_FALLBACK
#define AIOT_ALLOW_DEMO_FALLBACK 0
#endif

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastPublishAt = 0;

struct SensorSample {
  float value;
  bool available;
  const char *quality;
};

struct ComfortReading {
  bool valid;
  float temperatureC;
  float humidityPct;
  unsigned long updatedAt;
};

struct Scd4xReading {
  bool valid;
  float co2Ppm;
  float temperatureC;
  float humidityPct;
  unsigned long updatedAt;
};

ComfortReading sht31Cache = {false, NAN, NAN, 0};
Scd4xReading scd4xCache = {false, NAN, NAN, NAN, 0};
bool scd4xStarted = false;
unsigned long scd4xStartedAt = 0;

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

uint8_t crc8(const uint8_t *data, const size_t length) {
  uint8_t crc = 0xFF;
  for (size_t index = 0; index < length; index += 1) {
    crc ^= data[index];
    for (uint8_t bit = 0; bit < 8; bit += 1) {
      if ((crc & 0x80) != 0) {
        crc = static_cast<uint8_t>((crc << 1) ^ 0x31);
      } else {
        crc <<= 1;
      }
    }
  }
  return crc;
}

bool writeI2cCommand(const uint8_t address, const uint16_t command) {
  Wire.beginTransmission(address);
  Wire.write(static_cast<uint8_t>(command >> 8));
  Wire.write(static_cast<uint8_t>(command & 0xFF));
  return Wire.endTransmission() == 0;
}

bool requestI2cBytes(const uint8_t address, uint8_t *buffer, const size_t length) {
  const size_t received = Wire.requestFrom(static_cast<int>(address), static_cast<int>(length));
  if (received != length) {
    while (Wire.available()) {
      Wire.read();
    }
    return false;
  }

  for (size_t index = 0; index < length; index += 1) {
    buffer[index] = Wire.read();
  }
  return true;
}

bool readCrcWord(const uint8_t *buffer, uint16_t *value) {
  if (crc8(buffer, 2) != buffer[2]) {
    return false;
  }
  *value = static_cast<uint16_t>((buffer[0] << 8) | buffer[1]);
  return true;
}

SensorSample sampleUnavailable() {
  return {NAN, false, "stale"};
}

SensorSample sampleValue(const float value, const char *quality = "ok") {
  return {value, std::isfinite(value), quality};
}

SensorSample demoFallback(const float value) {
#if AIOT_ALLOW_DEMO_FALLBACK
  return {value, true, "stale"};
#else
  return sampleUnavailable();
#endif
}

float analogRatio(const int pin) {
  const int raw = analogRead(pin);
  return static_cast<float>(raw) / 4095.0f;
}

bool refreshSht31() {
#if AIOT_USE_SHT31
  const unsigned long currentMs = millis();
  if (sht31Cache.valid && currentMs - sht31Cache.updatedAt < 2000) {
    return true;
  }

  if (!writeI2cCommand(AIOT_SHT31_ADDRESS, 0x2400)) {
    sht31Cache.valid = false;
    return false;
  }
  delay(20);

  uint8_t buffer[6] = {0};
  uint16_t rawTemperature = 0;
  uint16_t rawHumidity = 0;
  if (!requestI2cBytes(AIOT_SHT31_ADDRESS, buffer, sizeof(buffer)) ||
      !readCrcWord(buffer, &rawTemperature) ||
      !readCrcWord(buffer + 3, &rawHumidity)) {
    sht31Cache.valid = false;
    return false;
  }

  sht31Cache.temperatureC = -45.0f + 175.0f * static_cast<float>(rawTemperature) / 65535.0f;
  sht31Cache.humidityPct = 100.0f * static_cast<float>(rawHumidity) / 65535.0f;
  sht31Cache.updatedAt = currentMs;
  sht31Cache.valid = std::isfinite(sht31Cache.temperatureC) && std::isfinite(sht31Cache.humidityPct);
  return sht31Cache.valid;
#else
  return false;
#endif
}

bool readBh1750Lux(float *lux) {
#if AIOT_USE_BH1750
  Wire.beginTransmission(AIOT_BH1750_ADDRESS);
  Wire.write(0x20);
  if (Wire.endTransmission() != 0) {
    return false;
  }
  delay(180);

  uint8_t buffer[2] = {0};
  if (!requestI2cBytes(AIOT_BH1750_ADDRESS, buffer, sizeof(buffer))) {
    return false;
  }
  const uint16_t raw = static_cast<uint16_t>((buffer[0] << 8) | buffer[1]);
  *lux = static_cast<float>(raw) / 1.2f;
  return std::isfinite(*lux);
#else
  return false;
#endif
}

void startScd4x() {
#if AIOT_USE_SCD4X
  writeI2cCommand(AIOT_SCD4X_ADDRESS, 0x3F86);
  delay(500);
  scd4xStarted = writeI2cCommand(AIOT_SCD4X_ADDRESS, 0x21B1);
  scd4xStartedAt = millis();
#endif
}

bool refreshScd4x() {
#if AIOT_USE_SCD4X
  const unsigned long currentMs = millis();
  if (scd4xCache.valid && currentMs - scd4xCache.updatedAt < 5000) {
    return true;
  }
  if (!scd4xStarted || currentMs - scd4xStartedAt < 5000) {
    return false;
  }
  if (!writeI2cCommand(AIOT_SCD4X_ADDRESS, 0xEC05)) {
    scd4xCache.valid = false;
    return false;
  }
  delay(5);

  uint8_t buffer[9] = {0};
  uint16_t rawCo2 = 0;
  uint16_t rawTemperature = 0;
  uint16_t rawHumidity = 0;
  if (!requestI2cBytes(AIOT_SCD4X_ADDRESS, buffer, sizeof(buffer)) ||
      !readCrcWord(buffer, &rawCo2) ||
      !readCrcWord(buffer + 3, &rawTemperature) ||
      !readCrcWord(buffer + 6, &rawHumidity) ||
      rawCo2 == 0) {
    scd4xCache.valid = false;
    return false;
  }

  scd4xCache.co2Ppm = static_cast<float>(rawCo2);
  scd4xCache.temperatureC = -45.0f + 175.0f * static_cast<float>(rawTemperature) / 65535.0f;
  scd4xCache.humidityPct = 100.0f * static_cast<float>(rawHumidity) / 65535.0f;
  scd4xCache.updatedAt = currentMs;
  scd4xCache.valid =
      std::isfinite(scd4xCache.co2Ppm) &&
      std::isfinite(scd4xCache.temperatureC) &&
      std::isfinite(scd4xCache.humidityPct);
  return scd4xCache.valid;
#else
  return false;
#endif
}

SensorSample readTemperatureC() {
  if (refreshSht31()) {
    return sampleValue(sht31Cache.temperatureC);
  }
  if (refreshScd4x()) {
    return sampleValue(scd4xCache.temperatureC);
  }
  return demoFallback(25.0f);
}

SensorSample readHumidityPct() {
  if (refreshSht31()) {
    return sampleValue(sht31Cache.humidityPct);
  }
  if (refreshScd4x()) {
    return sampleValue(scd4xCache.humidityPct);
  }
  return demoFallback(48.0f);
}

SensorSample readCo2Ppm() {
  if (refreshScd4x()) {
    return sampleValue(scd4xCache.co2Ppm, scd4xCache.co2Ppm > 1200.0f ? "anomaly" : "ok");
  }
#if AIOT_USE_ANALOG_CO2
  const int raw = analogRead(AIOT_CO2_ADC_PIN);
  const float ratio = static_cast<float>(raw) / 4095.0f;
  const float ppm = AIOT_ANALOG_CO2_MIN_PPM + ratio * (AIOT_ANALOG_CO2_MAX_PPM - AIOT_ANALOG_CO2_MIN_PPM);
  return sampleValue(ppm, ppm > 1200.0f ? "anomaly" : "ok");
#else
  return demoFallback(500.0f);
#endif
}

SensorSample readLightLux() {
  float lux = NAN;
  if (readBh1750Lux(&lux)) {
    return sampleValue(lux);
  }
#if AIOT_USE_ANALOG_LIGHT
  return sampleValue(analogRatio(AIOT_LIGHT_ADC_PIN) * AIOT_ANALOG_LIGHT_MAX_LUX);
#else
  return demoFallback(420.0f);
#endif
}

SensorSample readPresence() {
  return sampleValue(digitalRead(AIOT_PRESENCE_PIN) == HIGH ? 1.0f : 0.0f);
}

SensorSample readNoiseDbA() {
#if AIOT_USE_ANALOG_NOISE
  const float db = AIOT_ANALOG_NOISE_MIN_DB +
                   analogRatio(AIOT_NOISE_ADC_PIN) * (AIOT_ANALOG_NOISE_MAX_DB - AIOT_ANALOG_NOISE_MIN_DB);
  return sampleValue(db, db > 65.0f ? "anomaly" : "ok");
#else
  return demoFallback(48.5f);
#endif
}

void addReading(JsonArray readings, const char *metric, float value, const char *unit, const char *quality = "ok") {
  JsonObject reading = readings.add<JsonObject>();
  reading["metric"] = metric;
  reading["value"] = value;
  reading["unit"] = unit;
  reading["quality"] = quality;
}

void addReading(JsonArray readings, const char *metric, const SensorSample sample, const char *unit) {
  if (!sample.available) {
    Serial.printf("skip metric=%s reason=sensor_unavailable\n", metric);
    return;
  }
  addReading(readings, metric, sample.value, unit, sample.quality);
}

bool publishTelemetry() {
  StaticJsonDocument<1024> payload;
  payload["device_id"] = AIOT_DEVICE_ID;
  JsonArray readings = payload["readings"].to<JsonArray>();

  addReading(readings, "temperature", readTemperatureC(), "\xE2\x84\x83");
  addReading(readings, "humidity", readHumidityPct(), "%");
  addReading(readings, "co2", readCo2Ppm(), "ppm");
  addReading(readings, "light", readLightLux(), "lux");
  addReading(readings, "presence", readPresence(), "occupied");
  addReading(readings, "noise", readNoiseDbA(), "dB");

  if (readings.size() == 0) {
    Serial.println("skip publish reason=no_sensor_readings");
    return false;
  }

  char buffer[1024];
  const size_t size = serializeJson(payload, buffer, sizeof(buffer));
  const String topic = telemetryTopic();
  const bool ok = mqttClient.publish(topic.c_str(), reinterpret_cast<const uint8_t *>(buffer), size, false);
  Serial.printf("publish topic=%s bytes=%u ok=%s\n", topic.c_str(), static_cast<unsigned>(size), ok ? "true" : "false");
  return ok;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(AIOT_I2C_SDA_PIN, AIOT_I2C_SCL_PIN);
  pinMode(AIOT_PRESENCE_PIN, INPUT);
  analogReadResolution(12);
  startScd4x();
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
