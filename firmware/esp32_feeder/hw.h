#pragma once

#include <Arduino.h>

namespace hw {

struct DisplayData {
  const char *state;
  float distanceCm;  // < 0 when the reading is invalid
  int feedPct;       // < 0 when unknown
  bool wifiOk;
  bool mqttOk;
  int thresholdPct;
  int scheduleCount;
  bool clockValid;
};

// Detects every I2C peripheral; missing parts degrade gracefully.
void begin();

bool servoReady();
void servoOpen();
void servoClose();

// < 0 when the sensor is absent, out of range, or not answering.
float readDistanceCm();

bool clockValid();
void clockNow(int &y, int &mo, int &d, int &h, int &mi, int &s);
// Returns true when the DS3231 was written, false when only the RAM clock was.
bool clockSet(int y, int mo, int d, int h, int mi, int s);
String clockIso();
String clockDate();
String clockTime();

void displaySplash(const char *line1, const char *line2);
void displayTick(const DisplayData &data, uint32_t nowMs);

}  // namespace hw
