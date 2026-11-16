#pragma once

// ===========================================================================
// Identity
// ===========================================================================
#define FW_VERSION "1.0.0"

// Device id = devices.device_code in the platform database.
//
// Left empty, it is derived from the chip's factory MAC, e.g. `feeder-64008c`
// (last 3 bytes of the STA MAC). Unique per board, survives reflashing, and is
// also what the platform shows in its device picker.
//
// Set an explicit value (e.g. "feeder01") to keep the seeded device row instead.
#define DEVICE_ID_OVERRIDE ""
#define DEVICE_ID_PREFIX "feeder"

// ===========================================================================
// Network
// ===========================================================================
// WIFI_SSID, WIFI_PASS and MQTT_HOST live in secrets.h — that file is
// gitignored so credentials never reach the repository. Copy
// secrets.h.example to secrets.h and fill it in.
#if __has_include("secrets.h")
#include "secrets.h"
#endif

#ifndef WIFI_SSID
#define WIFI_SSID ""
#define WIFI_PASS ""
#endif
#ifndef MQTT_HOST
#define MQTT_HOST "127.0.0.1"
#endif

// Optional auth/TLS — override these in secrets.h for a protected broker.
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif
#ifndef MQTT_USE_TLS
#define MQTT_USE_TLS 0
#endif
#ifndef MQTT_USER
#define MQTT_USER ""
#endif
#ifndef MQTT_PASS
#define MQTT_PASS ""
#endif

// Unique topic namespace so a public broker is not shared with other projects.
#define TOPIC_PREFIX "feeder-ayurahmaw"

// ===========================================================================
// Pins — ESP32-WROOM-32 DevKit V1 (30-pin)
// ===========================================================================
#define PIN_SERVO 13
#define PIN_TRIG 5
#define PIN_ECHO 18
#define PIN_SDA 21
#define PIN_SCL 22

// ===========================================================================
// Servo gate (SG90)
// ===========================================================================
#define SERVO_MIN_US 500
#define SERVO_MAX_US 2400
#define SERVO_CLOSED_DEG 0
#define SERVO_OPEN_DEG 90
#define SERVO_SETTLE_MS 300
#define PORTION_OPEN_MS 1000
#define PORTION_GAP_MS 200

// ===========================================================================
// Hopper calibration — keep in sync with the devices table
// ===========================================================================
#define HOPPER_FULL_CM 5.0f
#define HOPPER_EMPTY_CM 20.0f
#define MAX_DISTANCE_CM 40.0f

// ===========================================================================
// Timing (no delay() in loop(); everything is millis()-driven)
// ===========================================================================
#define SERIAL_BAUD 115200
#define TELEMETRY_INTERVAL_MS 15000UL
#define SENSOR_INTERVAL_MS 2000UL
#define MQTT_RETRY_MS 5000UL
#define DISPLAY_INTERVAL_MS 500UL
#define DISPLAY_PAGE_MS 4000UL

// ===========================================================================
// Schedules
// ===========================================================================
#define MAX_SCHEDULES 8
#define SCHEDULE_WINDOW_SEC 60

// ===========================================================================
// I2C + MQTT buffers
// ===========================================================================
#define I2C_ADDR_RTC 0x68
#define I2C_ADDR_LCD 0x27
#define I2C_ADDR_LCD_ALT 0x3F

#define MQTT_BUFFER_SIZE 1024
#define COMMAND_QUEUE_SIZE 4
#define DEFAULT_THRESHOLD_PCT 20

#define NVS_NAMESPACE "feeder"
