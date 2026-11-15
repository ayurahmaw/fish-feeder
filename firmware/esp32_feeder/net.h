#pragma once

#include <Arduino.h>
#include <PubSubClient.h>

typedef void (*CommandHandler)(const char *topic, const uint8_t *payload, unsigned int len);

namespace net {

extern PubSubClient client;

void begin(CommandHandler handler);
void tick();

bool wifiConnected();
bool connected();
int rssi();

// Device id, resolved once in begin() (MAC-derived unless overridden).
String deviceId();

// "feeder/<deviceId>/<kind>"
String topic(const char *kind);

bool publish(const String &topic, const String &payload, bool retained = false);

}  // namespace net
