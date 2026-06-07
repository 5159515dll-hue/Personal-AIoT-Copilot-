#include <cstdio>
#include <cstdint>

static const char *API_BASE_URL = "http://82.157.148.249";
static const char *DEVICE_ID = "stm32_room_node_01";
static const char *DEVICE_NAME = "STM32 房间节点";
static const char *FIRMWARE_VERSION = "0.1.0";

static uint32_t sequence_number = 1;

extern "C" uint32_t millis();
extern "C" bool aiot_transport_post_json(const char *url, const char *json_body);

static float read_temperature_c() {
  return 25.2f;
}

static float read_humidity_percent() {
  return 48.0f;
}

static float read_co2_ppm() {
  return 930.0f;
}

static void post_register() {
  char url[160];
  char body[768];
  std::snprintf(url, sizeof(url), "%s/api/device-connections/register", API_BASE_URL);
  std::snprintf(
      body,
      sizeof(body),
      "{"
      "\"device_id\":\"%s\","
      "\"display_name\":\"%s\","
      "\"device_type\":\"stm32\","
      "\"transport\":\"serial_gateway\","
      "\"protocol_version\":\"aiot.v1\","
      "\"firmware_version\":\"%s\","
      "\"hardware_revision\":\"stm32-generic\","
      "\"location\":\"desk\","
      "\"capabilities\":[{\"kind\":\"telemetry\",\"metrics\":[\"temperature\",\"humidity\",\"co2\"],\"description\":\"STM32 环境遥测\"}]"
      "}",
      DEVICE_ID,
      DEVICE_NAME,
      FIRMWARE_VERSION);
  aiot_transport_post_json(url, body);
}

static void post_heartbeat() {
  char url[180];
  char body[512];
  const uint32_t seq = sequence_number++;
  std::snprintf(url, sizeof(url), "%s/api/device-connections/%s/heartbeat", API_BASE_URL, DEVICE_ID);
  std::snprintf(
      body,
      sizeof(body),
      "{"
      "\"status\":\"online\","
      "\"transport\":\"serial_gateway\","
      "\"protocol_version\":\"aiot.v1\","
      "\"firmware_version\":\"%s\","
      "\"uptime_seconds\":%lu,"
      "\"message_id\":\"%s-hb-%lu\","
      "\"sequence\":%lu"
      "}",
      FIRMWARE_VERSION,
      static_cast<unsigned long>(millis() / 1000),
      DEVICE_ID,
      static_cast<unsigned long>(seq),
      static_cast<unsigned long>(seq));
  aiot_transport_post_json(url, body);
}

static void post_telemetry() {
  char url[180];
  char body[768];
  const uint32_t seq = sequence_number++;
  std::snprintf(url, sizeof(url), "%s/api/device-connections/%s/telemetry", API_BASE_URL, DEVICE_ID);
  std::snprintf(
      body,
      sizeof(body),
      "{"
      "\"protocol_version\":\"aiot.v1\","
      "\"message_id\":\"%s-tel-%lu\","
      "\"sequence\":%lu,"
      "\"firmware_version\":\"%s\","
      "\"readings\":["
      "{\"metric\":\"temperature\",\"value\":%.1f,\"unit\":\"℃\",\"quality\":\"ok\"},"
      "{\"metric\":\"humidity\",\"value\":%.1f,\"unit\":\"%%\",\"quality\":\"ok\"},"
      "{\"metric\":\"co2\",\"value\":%.1f,\"unit\":\"ppm\",\"quality\":\"ok\"}"
      "]"
      "}",
      DEVICE_ID,
      static_cast<unsigned long>(seq),
      static_cast<unsigned long>(seq),
      FIRMWARE_VERSION,
      read_temperature_c(),
      read_humidity_percent(),
      read_co2_ppm());
  aiot_transport_post_json(url, body);
}

void aiot_setup() {
  post_register();
}

void aiot_loop() {
  static uint32_t last_heartbeat_ms = 0;
  static uint32_t last_telemetry_ms = 0;
  const uint32_t now_ms = millis();

  if (now_ms - last_heartbeat_ms >= 30000) {
    post_heartbeat();
    last_heartbeat_ms = now_ms;
  }
  if (now_ms - last_telemetry_ms >= 60000) {
    post_telemetry();
    last_telemetry_ms = now_ms;
  }
}
