#include "protocol.h"

#include <ArduinoJson.h>
#include <Preferences.h>

#include "config.h"
#include "hw.h"
#include "net.h"

namespace proto {

namespace {

Preferences prefs;

int threshold = DEFAULT_THRESHOLD_PCT;
Schedule schedules[MAX_SCHEDULES];
int scheduleTotal = 0;

Command queue[COMMAND_QUEUE_SIZE];
int queueHead = 0;
int queueTail = 0;
int queueCount = 0;

uint32_t firedDateKey = 0;
uint32_t firedMask = 0;

void copyText(char *dst, size_t size, const char *src) {
  if (size == 0) {
    return;
  }
  if (src == nullptr) {
    dst[0] = '\0';
    return;
  }
  strncpy(dst, src, size - 1);
  dst[size - 1] = '\0';
}

void publishJson(const char *kind, JsonDocument &doc, size_t reserve = 256) {
  const size_t needed = measureJson(doc) + 1;
  if (needed > reserve) {
    Serial.printf("[mqtt] payload %s butuh %u byte > %u, dibuang\n", kind,
                  static_cast<unsigned>(needed), static_cast<unsigned>(reserve));
    return;
  }
  char *buf = static_cast<char *>(malloc(needed));
  if (buf == nullptr) {
    return;
  }
  const size_t written = serializeJson(doc, buf, needed);
  if (written > 0) {
    net::publish(net::topic(kind), String(buf, written));
  }
  free(buf);
}

bool parseSchedules(const char *json) {
  JsonDocument doc;
  if (deserializeJson(doc, json)) {
    return false;
  }
  JsonArray list = doc.as<JsonArray>();
  if (list.isNull()) {
    return false;
  }

  Schedule parsed[MAX_SCHEDULES];
  int count = 0;
  for (JsonObject entry : list) {
    if (count >= MAX_SCHEDULES) {
      break;
    }
    const char *when = entry["feed_time"] | "";
    if (strlen(when) != 8) {
      continue;
    }
    parsed[count].id = entry["id"] | 0;
    copyText(parsed[count].feedTime, sizeof(parsed[count].feedTime), when);
    parsed[count].portions = entry["portions"] | 1;
    if (parsed[count].portions < 1) {
      parsed[count].portions = 1;
    }
    if (parsed[count].portions > 10) {
      parsed[count].portions = 10;
    }
    count++;
  }

  for (int i = 0; i < count; i++) {
    schedules[i] = parsed[i];
  }
  scheduleTotal = count;
  return true;
}

}  // namespace

void begin() {
  prefs.begin(NVS_NAMESPACE, false);

  threshold = prefs.getInt("threshold", DEFAULT_THRESHOLD_PCT);
  firedDateKey = prefs.getUInt("fireDate", 0);
  firedMask = prefs.getUInt("fireMask", 0);

  const String blob = prefs.getString("schedules", "");
  if (blob.length() > 0) {
    parseSchedules(blob.c_str());
  }
  Serial.printf("[proto] threshold=%d%% schedules=%d\n", threshold, scheduleTotal);
}

void enqueue(const uint8_t *payload, unsigned int len) {
  if (queueCount >= COMMAND_QUEUE_SIZE) {
    Serial.println("[cmd] antrean penuh — perintah dibuang");
    return;
  }

  JsonDocument doc;
  const DeserializationError err = deserializeJson(doc, payload, len);
  if (err) {
    Serial.printf("[cmd] JSON tidak valid: %s\n", err.c_str());
    return;
  }

  Command &cmd = queue[queueTail];
  memset(&cmd, 0, sizeof(cmd));
  copyText(cmd.id, sizeof(cmd.id), doc["command_id"] | "");
  copyText(cmd.type, sizeof(cmd.type), doc["type"] | "");
  cmd.portions = doc["payload"]["portions"] | 1;
  cmd.thresholdPct = doc["payload"]["threshold_pct"] | -1;
  cmd.angle = doc["payload"]["angle"] | -1;
  copyText(cmd.datetime, sizeof(cmd.datetime), doc["payload"]["datetime"] | "");

  if (doc["payload"]["schedules"].is<JsonArray>()) {
    serializeJson(doc["payload"]["schedules"], cmd.schedulesJson,
                  sizeof(cmd.schedulesJson));
  }

  queueTail = (queueTail + 1) % COMMAND_QUEUE_SIZE;
  queueCount++;
  Serial.printf("[cmd] masuk type=%s id=%s\n", cmd.type, cmd.id);
}

bool pop(Command &out) {
  if (queueCount == 0) {
    return false;
  }
  out = queue[queueHead];
  queueHead = (queueHead + 1) % COMMAND_QUEUE_SIZE;
  queueCount--;
  return true;
}

void ack(const char *commandId, const char *result, const String &message) {
  JsonDocument doc;
  doc["command_id"] = commandId;
  doc["result"] = result;
  doc["message"] = message;
  if (hw::clockValid()) {
    doc["ts"] = hw::clockIso();
  }
  publishJson("ack", doc, 512);
  Serial.printf("[ack] %s -> %s (%s)\n", commandId, result, message.c_str());
}

void publishTelemetry(const char *state, float distanceCm, int feedPct) {
  JsonDocument doc;
  doc["device"] = net::deviceId();
  doc["state"] = state;
  if (distanceCm >= 0) {
    doc["distance_cm"] = roundf(distanceCm * 10.0f) / 10.0f;
  }
  if (feedPct >= 0) {
    doc["feed_level_pct"] = feedPct;
  }
  if (hw::clockValid()) {
    doc["ts"] = hw::clockIso();
  }
  publishJson("telemetry", doc, 256);
  Serial.printf("[telemetry] state=%s distance=%.1f pct=%d\n", state, distanceCm, feedPct);
}

bool publishScheduledFeed(int portions, const char *feedTime, float distanceCm) {
  JsonDocument doc;
  doc["event"] = "scheduled_feed";
  doc["device"] = net::deviceId();
  doc["portions"] = portions;
  doc["feed_time"] = feedTime;
  if (distanceCm >= 0) {
    doc["distance_cm"] = roundf(distanceCm * 10.0f) / 10.0f;
  }
  if (hw::clockValid()) {
    doc["ts"] = hw::clockIso();
  }
  publishJson("state", doc, 256);
  return true;
}

int thresholdPct() { return threshold; }

void setThresholdPct(int pct) {
  threshold = pct;
  prefs.putInt("threshold", threshold);
}

int scheduleCount() { return scheduleTotal; }

const Schedule *scheduleList() { return schedules; }

bool storeSchedules(const char *json, int &stored) {
  if (!parseSchedules(json)) {
    return false;
  }

  JsonDocument doc;
  JsonArray list = doc.to<JsonArray>();
  for (int i = 0; i < scheduleTotal; i++) {
    JsonObject entry = list.add<JsonObject>();
    entry["id"] = schedules[i].id;
    entry["feed_time"] = schedules[i].feedTime;
    entry["portions"] = schedules[i].portions;
  }

  char buf[512];
  const size_t written = serializeJson(doc, buf, sizeof(buf));
  if (written == 0 || written >= sizeof(buf)) {
    return false;
  }
  prefs.putString("schedules", String(buf, written));

  // Schedule indexes shifted: clear today's fired marks so nothing is skipped.
  firedMask = 0;
  prefs.putUInt("fireMask", firedMask);

  stored = scheduleTotal;
  return true;
}

bool wasFired(uint32_t dateKey, int index) {
  if (index < 0 || index >= 32 || dateKey != firedDateKey) {
    return false;
  }
  return (firedMask & (1UL << index)) != 0;
}

void markFired(uint32_t dateKey, int index) {
  if (index < 0 || index >= 32) {
    return;
  }
  if (dateKey != firedDateKey) {
    firedDateKey = dateKey;
    firedMask = 0;
    prefs.putUInt("fireDate", firedDateKey);
  }
  firedMask |= (1UL << index);
  prefs.putUInt("fireMask", firedMask);
}

}  // namespace proto
