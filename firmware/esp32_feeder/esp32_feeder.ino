// ESP32 aquaponic autofeeder — MQTT device for the Streamlit platform.
// Contract: CONTEXT.md §10 (topics, telemetry, command, ack).

#include <ArduinoJson.h>

#include "config.h"
#include "hw.h"
#include "net.h"
#include "protocol.h"

namespace {

enum FeedPhase : uint8_t { FEED_IDLE, FEED_OPEN, FEED_CLOSING, FEED_GAP };

FeedPhase phase = FEED_IDLE;
uint32_t phaseAt = 0;

int jobTotal = 0;
int jobRemaining = 0;
bool jobScheduled = false;
bool jobAckPending = false;
char jobFeedTime[9] = {0};
char jobAckId[48] = {0};

float distanceCm = -1;
int feedPct = -1;

uint32_t lastSensorAt = 0;
uint32_t lastTelemetryAt = 0;
uint32_t lastDisplayAt = 0;
uint32_t lastSecondAt = 0;

bool wasMqttConnected = false;
bool wasWifiConnected = false;

void onMqttMessage(const char *topic, const uint8_t *payload, unsigned int len);
const char *stateString();
void measureDistance();
void publishTelemetry();
bool feedStart(int portions, bool scheduled, const char *feedTime, const char *ackId);
void feedTick();
void handleCommand(const proto::Command &cmd);
String stateSnapshotJson();

bool parseHhMmSs(const char *text, int &h, int &m, int &s) {
  if (text == nullptr || strlen(text) < 8) {
    return false;
  }
  if (sscanf(text, "%2d:%2d:%2d", &h, &m, &s) != 3) {
    return false;
  }
  return h >= 0 && h < 24 && m >= 0 && m < 60 && s >= 0 && s < 60;
}

bool parseIsoLocal(const char *text, int &y, int &mo, int &d, int &h, int &mi, int &s) {
  if (text == nullptr || strlen(text) < 19) {
    return false;
  }
  if (sscanf(text, "%4d-%2d-%2dT%2d:%2d:%2d", &y, &mo, &d, &h, &mi, &s) != 6) {
    return false;
  }
  return y >= 2020 && mo >= 1 && mo <= 12 && d >= 1 && d <= 31 && h >= 0 && h < 24 &&
         mi >= 0 && mi < 60 && s >= 0 && s < 60;
}

int pctFromCm(float cm) {
  if (cm < 0) {
    return -1;
  }
  const float span = HOPPER_EMPTY_CM - HOPPER_FULL_CM;
  if (span <= 0) {
    return -1;
  }
  float pct = (HOPPER_EMPTY_CM - cm) / span * 100.0f;
  if (pct < 0.0f) {
    pct = 0.0f;
  }
  if (pct > 100.0f) {
    pct = 100.0f;
  }
  return static_cast<int>(pct + 0.5f);
}

void measureDistance() {
  distanceCm = hw::readDistanceCm();
  feedPct = pctFromCm(distanceCm);
}

const char *stateString() {
  if (phase != FEED_IDLE) {
    return "feeding";
  }
  if (distanceCm < 0) {
    return "error";
  }
  return "idle";
}

void publishTelemetry() {
  lastTelemetryAt = millis();
  proto::publishTelemetry(stateString(), distanceCm, feedPct);
}

void onMqttMessage(const char *topic, const uint8_t *payload, unsigned int len) {
  // The embedded broker can deliver retained messages of other topics, so filter.
  if (net::topic("command") != topic) {
    return;
  }
  proto::enqueue(payload, len);
}

bool feedStart(int portions, bool scheduled, const char *feedTime, const char *ackId) {
  if (phase != FEED_IDLE || !hw::servoReady()) {
    return false;
  }

  jobTotal = constrain(portions, 1, 10);
  jobRemaining = jobTotal;
  jobScheduled = scheduled;
  jobAckPending = (ackId != nullptr && ackId[0] != '\0');

  strncpy(jobAckId, ackId != nullptr ? ackId : "", sizeof(jobAckId) - 1);
  jobAckId[sizeof(jobAckId) - 1] = '\0';
  strncpy(jobFeedTime, feedTime != nullptr ? feedTime : "", sizeof(jobFeedTime) - 1);
  jobFeedTime[sizeof(jobFeedTime) - 1] = '\0';

  hw::servoOpen();
  phase = FEED_OPEN;
  phaseAt = millis();
  Serial.printf("[feed] %d porsi (%s)\n", jobTotal, scheduled ? "jadwal" : "manual");
  return true;
}

void finishFeed() {
  phase = FEED_IDLE;
  hw::servoClose();
  measureDistance();

  if (jobScheduled) {
    // Event first: the platform uses its latest telemetry row as the "before" level.
    proto::publishScheduledFeed(jobTotal, jobFeedTime, distanceCm);
    publishTelemetry();
  } else {
    // Telemetry first so attach_feed_level_after() sees the post-feed level.
    publishTelemetry();
    if (jobAckPending) {
      proto::ack(jobAckId, "ok", String("feeding ") + jobTotal + " portions");
    }
  }
  jobAckPending = false;
}

void feedTick() {
  if (phase == FEED_IDLE) {
    return;
  }
  const uint32_t now = millis();

  switch (phase) {
    case FEED_OPEN:
      if (now - phaseAt >= PORTION_OPEN_MS) {
        hw::servoClose();
        phase = FEED_CLOSING;
        phaseAt = now;
      }
      break;
    case FEED_CLOSING:
      if (now - phaseAt >= SERVO_SETTLE_MS) {
        jobRemaining--;
        if (jobRemaining > 0) {
          phase = FEED_GAP;
          phaseAt = now;
        } else {
          finishFeed();
        }
      }
      break;
    case FEED_GAP:
      if (now - phaseAt >= PORTION_GAP_MS) {
        hw::servoOpen();
        phase = FEED_OPEN;
        phaseAt = now;
      }
      break;
    default:
      break;
  }
}

void commandTick() {
  proto::Command cmd;
  if (proto::pop(cmd)) {
    handleCommand(cmd);
  }
}

void handleCommand(const proto::Command &cmd) {
  if (strcmp(cmd.type, "manual_feed") == 0) {
    if (phase != FEED_IDLE) {
      proto::ack(cmd.id, "error_busy", "feeding in progress");
      return;
    }
    if (!hw::servoReady()) {
      proto::ack(cmd.id, "error_servo", "servo not attached");
      return;
    }
    if (feedPct == 0) {
      proto::ack(cmd.id, "error_low_level", "hopper empty");
      return;
    }
    feedStart(cmd.portions, false, "", cmd.id);
    return;
  }

  if (strcmp(cmd.type, "set_schedule") == 0) {
    int stored = 0;
    if (proto::storeSchedules(cmd.schedulesJson, stored)) {
      proto::ack(cmd.id, "ok", String("schedules stored: ") + stored);
    } else {
      proto::ack(cmd.id, "error_bad_payload", "schedules invalid");
    }
    return;
  }

  if (strcmp(cmd.type, "set_threshold") == 0) {
    if (cmd.thresholdPct < 0 || cmd.thresholdPct > 100) {
      proto::ack(cmd.id, "error_bad_payload", "threshold_pct missing");
      return;
    }
    proto::setThresholdPct(cmd.thresholdPct);
    proto::ack(cmd.id, "ok", String("threshold ") + cmd.thresholdPct + "%");
    return;
  }

  if (strcmp(cmd.type, "set_rtc") == 0) {
    int y, mo, d, h, mi, s;
    if (!parseIsoLocal(cmd.datetime, y, mo, d, h, mi, s)) {
      proto::ack(cmd.id, "error_bad_payload", "datetime invalid");
      return;
    }
    const bool rtcWritten = hw::clockSet(y, mo, d, h, mi, s);
    proto::ack(cmd.id, "ok", rtcWritten ? "rtc set" : "rtc absent; internal clock");
    return;
  }

  if (strcmp(cmd.type, "get_state") == 0) {
    proto::ack(cmd.id, "ok", stateSnapshotJson());
    return;
  }

  proto::ack(cmd.id, "error_unknown_type", cmd.type);
}

String stateSnapshotJson() {
  JsonDocument doc;
  doc["state"] = stateString();
  if (distanceCm >= 0) {
    doc["distance_cm"] = roundf(distanceCm * 10.0f) / 10.0f;
  }
  if (feedPct >= 0) {
    doc["feed_level_pct"] = feedPct;
  }
  if (hw::clockValid()) {
    doc["rtc"] = hw::clockIso();
  }
  doc["threshold"] = proto::thresholdPct();
  doc["schedules"] = proto::scheduleCount();
  doc["rssi"] = net::rssi();
  doc["fw"] = FW_VERSION;

  String out;
  serializeJson(doc, out);
  return out;
}

void sensorTick() {
  const uint32_t now = millis();
  if (now - lastSensorAt < SENSOR_INTERVAL_MS) {
    return;
  }
  lastSensorAt = now;
  measureDistance();
}

void scheduleTick() {
  const uint32_t now = millis();
  if (now - lastSecondAt < 1000) {
    return;
  }
  lastSecondAt = now;
  if (!hw::clockValid()) {
    return;
  }

  int y, mo, d, h, mi, s;
  hw::clockNow(y, mo, d, h, mi, s);
  const uint32_t dateKey = static_cast<uint32_t>(y) * 10000UL +
                           static_cast<uint32_t>(mo) * 100UL +
                           static_cast<uint32_t>(d);

  for (int i = 0; i < proto::scheduleCount(); i++) {
    const proto::Schedule &entry = proto::scheduleList()[i];

    int sh, sm, ss;
    if (!parseHhMmSs(entry.feedTime, sh, sm, ss)) {
      continue;
    }
    if (h != sh || mi != sm || s >= SCHEDULE_WINDOW_SEC) {
      continue;
    }
    if (proto::wasFired(dateKey, i)) {
      continue;
    }
    if (phase != FEED_IDLE) {
      continue;  // retry next second, still inside the 60 s window
    }
    if (!hw::servoReady()) {
      proto::markFired(dateKey, i);
      Serial.println("[sched] servo tidak terpasang — jadwal dilewati");
      continue;
    }
    if (feedPct == 0) {
      proto::markFired(dateKey, i);
      Serial.println("[sched] pakan habis — jadwal dilewati");
      continue;
    }
    if (feedStart(entry.portions, true, entry.feedTime, nullptr)) {
      proto::markFired(dateKey, i);
    }
  }
}

void telemetryTick() {
  const uint32_t now = millis();
  if (now - lastTelemetryAt < TELEMETRY_INTERVAL_MS) {
    return;
  }
  publishTelemetry();
}

void displayTick() {
  const uint32_t now = millis();
  if (now - lastDisplayAt < DISPLAY_INTERVAL_MS) {
    return;
  }
  lastDisplayAt = now;

  hw::DisplayData data;
  data.state = stateString();
  data.distanceCm = distanceCm;
  data.feedPct = feedPct;
  data.wifiOk = net::wifiConnected();
  data.mqttOk = net::connected();
  data.thresholdPct = proto::thresholdPct();
  data.scheduleCount = proto::scheduleCount();
  data.clockValid = hw::clockValid();
  hw::displayTick(data, now);
}

}  // namespace

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(300);
  Serial.printf("\n[feeder] fw %s\n", FW_VERSION);

  hw::begin();
  proto::begin();
  net::begin(onMqttMessage);
  hw::displaySplash(net::deviceId().c_str(), "starting...");
  measureDistance();
}

void loop() {
  net::tick();

  if (net::connected() && !wasMqttConnected) {
    publishTelemetry();
    Serial.println("[mqtt] siap — telemetry awal terkirim");
  }
  wasMqttConnected = net::connected();

  if (net::wifiConnected() && !wasWifiConnected) {
    Serial.printf("[wifi] terhubung, rssi %d dBm\n", net::rssi());
  }
  wasWifiConnected = net::wifiConnected();

  commandTick();
  feedTick();
  sensorTick();
  scheduleTick();
  telemetryTick();
  displayTick();
}
