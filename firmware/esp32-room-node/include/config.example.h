#pragma once

// Copy this file to include/config.h before building.
// Do not commit real Wi-Fi or MQTT credentials.

#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASSWORD "your-wifi-password"

#define MQTT_HOST "192.168.1.10"
#define MQTT_PORT 1883
#define MQTT_USERNAME ""
#define MQTT_PASSWORD ""

#define AIOT_ROOM_ID "001"
#define AIOT_DEVICE_ID "room_node_01"

#define AIOT_SAMPLE_INTERVAL_MS 60000

// I2C bus. ESP32-S3 DevKitC commonly uses GPIO 8/9, but adjust to your wiring.
#define AIOT_I2C_SDA_PIN 8
#define AIOT_I2C_SCL_PIN 9

// Real digital sensors. Enable only the hardware you actually connected.
#define AIOT_USE_SHT31 1
#define AIOT_SHT31_ADDRESS 0x44

#define AIOT_USE_BH1750 1
#define AIOT_BH1750_ADDRESS 0x23

#define AIOT_USE_SCD4X 1
#define AIOT_SCD4X_ADDRESS 0x62

// GPIO presence sensor. Use PIR or mmWave module digital output.
#define AIOT_PRESENCE_PIN 6

// Optional analog fallback sensors. Keep disabled unless calibrated on your hardware.
#define AIOT_USE_ANALOG_CO2 0
#define AIOT_CO2_ADC_PIN 5
#define AIOT_ANALOG_CO2_MIN_PPM 400.0f
#define AIOT_ANALOG_CO2_MAX_PPM 2000.0f

#define AIOT_USE_ANALOG_LIGHT 0
#define AIOT_LIGHT_ADC_PIN 4
#define AIOT_ANALOG_LIGHT_MAX_LUX 1200.0f

#define AIOT_USE_ANALOG_NOISE 0
#define AIOT_NOISE_ADC_PIN 7
#define AIOT_ANALOG_NOISE_MIN_DB 32.0f
#define AIOT_ANALOG_NOISE_MAX_DB 88.0f

// Disabled by default so missing sensors do not produce fake "ok" data.
// Set to 1 only for bench demos without hardware; fallback readings are marked stale.
#define AIOT_ALLOW_DEMO_FALLBACK 0
