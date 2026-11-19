#pragma once

#include <Arduino.h>

namespace proto {

struct Command {
  char id[48];
  char type[24];
  int portions;
  int thresholdPct;
  int angle;
  char datetime[24];
  char schedulesJson[512];
};

struct Schedule {
  int id;
  char feedTime[9];
  int portions;
};

void begin();

// Parsed on arrival so the callback only does cheap work.
void enqueue(const uint8_t *payload, unsigned int len);
bool pop(Command &out);

void ack(const char *commandId, const char *result, const String &message);
void publishTelemetry(const char *state, float distanceCm, int feedPct);
bool publishScheduledFeed(int portions, const char *feedTime, float distanceCm);

int thresholdPct();
void setThresholdPct(int pct);

int scheduleCount();
const Schedule *scheduleList();
bool storeSchedules(const char *json, int &stored);

bool wasFired(uint32_t dateKey, int index);
void markFired(uint32_t dateKey, int index);

}  // namespace proto
