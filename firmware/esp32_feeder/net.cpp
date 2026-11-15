#include "net.h"

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_mac.h>

#include "config.h"

namespace net {

namespace {
#if MQTT_USE_TLS
WiFiClientSecure transport;
#else
WiFiClient transport;
#endif
}  // namespace

// Must be constructed with the transport: the default PubSubClient() leaves
// _client null and the first connected() call faults.
PubSubClient client(transport);

namespace {

CommandHandler commandHandler = nullptr;
bool triedOnce = false;
unsigned long lastAttemptAt = 0;
unsigned long lastWifiLogAt = 0;
String deviceIdValue;

void resolveDeviceId() {
  if (strlen(DEVICE_ID_OVERRIDE) > 0) {
    deviceIdValue = DEVICE_ID_OVERRIDE;
    return;
  }
  // eFuse, not WiFi.macAddress(): the WiFi stack is not up yet at this point and
  // returns an all-zero buffer.
  uint8_t mac[6] = {0};
  if (esp_efuse_mac_get_default(mac) != ESP_OK) {
    Serial.println("[id] gagal membaca MAC — memakai id fallback");
    deviceIdValue = String(DEVICE_ID_PREFIX) + "-unknown";
    return;
  }
  char buf[32];
  snprintf(buf, sizeof(buf), "%s-%02x%02x%02x", DEVICE_ID_PREFIX, mac[3], mac[4], mac[5]);
  deviceIdValue = buf;
  Serial.printf("[id] mac %02x:%02x:%02x:%02x:%02x:%02x\n", mac[0], mac[1], mac[2], mac[3],
                mac[4], mac[5]);
}

void logWifiState() {
  const unsigned long now = millis();
  if (lastWifiLogAt != 0 && now - lastWifiLogAt < 10000) {
    return;
  }
  lastWifiLogAt = now;
  Serial.printf("[wifi] status=%d ssid=\"%s\"\n", WiFi.status(), WIFI_SSID);
}

void logVisibleNetworks() {
  Serial.println("[wifi] hasil scan (2.4 GHz yang terlihat):");
  const int found = WiFi.scanNetworks();
  if (found <= 0) {
    Serial.println("[wifi]   tidak ada jaringan terdeteksi");
    return;
  }
  for (int i = 0; i < found; i++) {
    Serial.printf("[wifi]   ch=%2d rssi=%4d  %s\n", WiFi.channel(i), WiFi.RSSI(i),
                  WiFi.SSID(i).c_str());
  }
}

void onMqttMessage(char *topic, byte *payload, unsigned int len) {
  if (commandHandler != nullptr) {
    commandHandler(topic, payload, len);
  }
}

bool connectOnce() {
  const unsigned long now = millis();
  if (triedOnce && now - lastAttemptAt < MQTT_RETRY_MS) {
    return false;
  }
  triedOnce = true;
  lastAttemptAt = now;

  const String statusTopic = topic("status");
  const String commandTopic = topic("command");

  // LWT: broker publishes "offline" (retained) if this device drops.
  bool ok;
  if (strlen(MQTT_USER) > 0) {
    ok = client.connect(deviceIdValue.c_str(), MQTT_USER, MQTT_PASS, statusTopic.c_str(), 0,
                        true, "offline");
  } else {
    ok = client.connect(deviceIdValue.c_str(), nullptr, nullptr, statusTopic.c_str(), 0, true,
                        "offline");
  }
  if (!ok) {
    Serial.printf("[mqtt] connect gagal rc=%d\n", client.state());
    return false;
  }

  client.publish(statusTopic.c_str(), "online", true);
  client.subscribe(commandTopic.c_str(), 1);
  Serial.printf("[mqtt] tersambung, birth online, subscribe %s\n", commandTopic.c_str());
  return true;
}

}  // namespace

void begin(CommandHandler handler) {
  commandHandler = handler;

  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);

  resolveDeviceId();
  WiFi.setHostname(deviceIdValue.c_str());
  Serial.printf("[id] device=%s\n", deviceIdValue.c_str());
  if (strlen(WIFI_SSID) == 0) {
    Serial.println("[wifi] WIFI_SSID kosong — salin secrets.h.example menjadi secrets.h");
  }

  logVisibleNetworks();
  WiFi.begin(WIFI_SSID, WIFI_PASS);

#if MQTT_USE_TLS
  // Encryption without pinning a CA bundle; pair with username/password.
  transport.setInsecure();
#endif
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setBufferSize(MQTT_BUFFER_SIZE);
  client.setKeepAlive(60);
  client.setSocketTimeout(10);
  client.setCallback(onMqttMessage);
}

void tick() {
  if (WiFi.status() != WL_CONNECTED) {
    logWifiState();
    if (client.connected()) {
      client.disconnect();
    }
    return;
  }
  if (!client.connected()) {
    connectOnce();
  }
  client.loop();
}

bool wifiConnected() { return WiFi.status() == WL_CONNECTED; }

bool connected() { return client.connected(); }

int rssi() { return WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0; }

String deviceId() { return deviceIdValue; }

String topic(const char *kind) {
  return String(TOPIC_PREFIX) + "/" + deviceIdValue + "/" + kind;
}

bool publish(const String &topic, const String &payload, bool retained) {
  if (!client.connected()) {
    return false;
  }
  return client.publish(topic.c_str(), payload.c_str(), retained);
}

}  // namespace net
