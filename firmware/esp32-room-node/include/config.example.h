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

// Optional analog pins. Replace these with your actual sensor wiring.
#define AIOT_LIGHT_ADC_PIN 4
#define AIOT_CO2_ADC_PIN 5
#define AIOT_NOISE_ADC_PIN 7
#define AIOT_PRESENCE_PIN 6
