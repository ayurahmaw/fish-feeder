#pragma once

#include <Arduino.h>

namespace hw {

struct DisplayData {
  float distanceCm;  // < 0 when the reading is invalid
  int feedPct;       // < 0 when unknown
  bool wifiOk;
  bool mqttOk;
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
// Same as displaySplash, but displayTick() leaves it on screen until nowMs + holdMs.
void displaySplashHold(const char *line1, const char *line2, uint32_t nowMs, uint32_t holdMs);
void displayTick(const DisplayData &data, uint32_t nowMs);

}  // namespace hw
