#include "hw.h"

#include <ESP32Servo.h>
#include <LiquidCrystal_I2C.h>
#include <RTClib.h>
#include <Wire.h>

#include "config.h"

namespace hw {

namespace {

Servo servo;
bool servoAttached = false;

RTC_DS3231 rtc;
bool rtcPresent = false;
bool rtcReady = false;

LiquidCrystal_I2C *lcd = nullptr;
bool lcdReady = false;

bool ramClockSet = false;
int64_t ramEpoch = 0;
uint32_t ramBaseMs = 0;

uint8_t page = 0;
uint32_t pageAt = 0;

int64_t daysFromCivil(int y, unsigned m, unsigned d) {
  y -= m <= 2;
  const int64_t era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + static_cast<int64_t>(doe) - 719468;
}

int64_t toEpoch(int y, int mo, int d, int h, int mi, int s) {
  return daysFromCivil(y, static_cast<unsigned>(mo), static_cast<unsigned>(d)) * 86400 +
         h * 3600 + mi * 60 + s;
}

void fromEpoch(int64_t t, int &y, int &mo, int &d, int &h, int &mi, int &s) {
  int64_t days = t / 86400;
  int64_t rem = t % 86400;
  if (rem < 0) {
    rem += 86400;
    days -= 1;
  }

  const int64_t z = days + 719468;
  const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
  const unsigned doe = static_cast<unsigned>(z - era * 146097);
  const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  const int64_t yy = static_cast<int64_t>(yoe) + era * 400;
  const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const unsigned mp = (5 * doy + 2) / 153;
  const unsigned dd = doy - (153 * mp + 2) / 5 + 1;
  const unsigned mm = mp + (mp < 10 ? 3 : -9);

  y = static_cast<int>(yy + (mm <= 2));
  mo = static_cast<int>(mm);
  d = static_cast<int>(dd);
  h = static_cast<int>(rem / 3600);
  mi = static_cast<int>((rem % 3600) / 60);
  s = static_cast<int>(rem % 60);
}

float readOnce() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  const unsigned long us = pulseIn(PIN_ECHO, HIGH, 30000UL);
  if (us == 0) {
    return -1;
  }
  const float cm = us / 58.0f;
  if (cm < 2.0f || cm > MAX_DISTANCE_CM) {
    return -1;
  }
  return cm;
}

String pad16(const String &text) {
  String out = text.substring(0, 16);
  while (out.length() < 16) {
    out += ' ';
  }
  return out;
}

void drawLine(uint8_t row, const String &text) {
  if (lcd == nullptr) {
    return;
  }
  // Redraw every tick: an I2C glitch (servo current spike) corrupts the
  // display until the next write, so the text must not be cached.
  lcd->setCursor(0, row);
  lcd->print(pad16(text));
}

void detectI2c() {
  Serial.println("[i2c] scan bus:");
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("[i2c]   0x%02X\n", addr);
    }
  }
}

}  // namespace

void begin() {
  Wire.begin(PIN_SDA, PIN_SCL);
  detectI2c();

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  digitalWrite(PIN_TRIG, LOW);

  servo.setPeriodHertz(50);
  servo.attach(PIN_SERVO, SERVO_MIN_US, SERVO_MAX_US);
  servoAttached = servo.attached();
  if (servoAttached) {
    servo.write(SERVO_CLOSED_DEG);
    Serial.println("[servo] siap");
  } else {
    Serial.println("[servo] tidak terpasang");
  }

  rtcPresent = rtc.begin();
  if (!rtcPresent) {
    Serial.println("[rtc] DS3231 tidak terdeteksi — memakai jam internal");
  } else if (rtc.lostPower()) {
    Serial.println("[rtc] lost power — jam belum valid, kirim set_rtc dari dashboard");
  } else {
    rtcReady = true;
    Serial.println("[rtc] DS3231 siap");
  }

  Wire.beginTransmission(I2C_ADDR_LCD);
  if (Wire.endTransmission() == 0) {
    lcd = new LiquidCrystal_I2C(I2C_ADDR_LCD, 16, 2);
  } else {
    Wire.beginTransmission(I2C_ADDR_LCD_ALT);
    if (Wire.endTransmission() == 0) {
      lcd = new LiquidCrystal_I2C(I2C_ADDR_LCD_ALT, 16, 2);
    }
  }
  if (lcd != nullptr) {
    lcd->init();
    lcd->backlight();
    lcd->clear();
    lcdReady = true;
    Serial.println("[lcd] LCD1602 siap");
  } else {
    Serial.println("[lcd] LCD1602 tidak terdeteksi");
  }
}

bool servoReady() { return servoAttached; }

void servoOpen() {
  if (servoAttached) {
    servo.write(SERVO_OPEN_DEG);
  }
}

void servoClose() {
  if (servoAttached) {
    servo.write(SERVO_CLOSED_DEG);
  }
}

float readDistanceCm() {
  float values[3];
  int valid = 0;

  for (int i = 0; i < 3; i++) {
    const float cm = readOnce();
    if (cm > 0) {
      values[valid++] = cm;
    } else if (i >= 1 && valid == 0) {
      break;
    }
  }
  if (valid == 0) {
    return -1;
  }
  if (valid == 1) {
    return values[0];
  }
  if (valid == 2) {
    return (values[0] + values[1]) / 2.0f;
  }
  if (values[0] > values[1]) {
    const float t = values[0];
    values[0] = values[1];
    values[1] = t;
  }
  if (values[1] > values[2]) {
    const float t = values[1];
    values[1] = values[2];
    values[2] = t;
  }
  if (values[0] > values[1]) {
    const float t = values[0];
    values[0] = values[1];
    values[1] = t;
  }
  return values[1];
}

bool clockValid() { return rtcReady || ramClockSet; }

void clockNow(int &y, int &mo, int &d, int &h, int &mi, int &s) {
  if (rtcReady) {
    const DateTime now = rtc.now();
    y = now.year();
    mo = now.month();
    d = now.day();
    h = now.hour();
    mi = now.minute();
    s = now.second();
    return;
  }
  if (!ramClockSet) {
    y = mo = d = h = mi = s = 0;
    return;
  }
  const int64_t elapsed = static_cast<int64_t>((millis() - ramBaseMs) / 1000UL);
  fromEpoch(ramEpoch + elapsed, y, mo, d, h, mi, s);
}

bool clockSet(int y, int mo, int d, int h, int mi, int s) {
  ramEpoch = toEpoch(y, mo, d, h, mi, s);
  ramBaseMs = millis();
  ramClockSet = true;

  if (!rtcPresent) {
    return false;
  }
  rtc.adjust(DateTime(y, mo, d, h, mi, s));
  rtcReady = true;
  return true;
}

String clockIso() {
  if (!clockValid()) {
    return "";
  }
  int y, mo, d, h, mi, s;
  clockNow(y, mo, d, h, mi, s);
  char buf[20];
  snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d", y, mo, d, h, mi, s);
  return String(buf);
}

String clockDate() {
  if (!clockValid()) {
    return "--/--";
  }
  int y, mo, d, h, mi, s;
  clockNow(y, mo, d, h, mi, s);
  char buf[6];
  snprintf(buf, sizeof(buf), "%02d/%02d", d, mo);
  return String(buf);
}

String clockTime() {
  if (!clockValid()) {
    return "--:--:--";
  }
  int y, mo, d, h, mi, s;
  clockNow(y, mo, d, h, mi, s);
  char buf[9];
  snprintf(buf, sizeof(buf), "%02d:%02d:%02d", h, mi, s);
  return String(buf);
}

void displaySplash(const char *line1, const char *line2) {
  if (!lcdReady) {
    return;
  }
  lcd->clear();
  drawLine(0, line1);
  drawLine(1, line2);
}

void displayTick(const DisplayData &data, uint32_t nowMs) {
  if (!lcdReady) {
    return;
  }
  if (nowMs - pageAt >= DISPLAY_PAGE_MS) {
    page = (page + 1) % 2;
    pageAt = nowMs;
  }

  String first;
  String second;

  if (page == 0) {
    first = "Pakan ";
    first += data.feedPct >= 0 ? String(data.feedPct) + "%" : String("--");
    first += "  ";
    first += data.distanceCm >= 0 ? String(data.distanceCm, 1) + "cm" : String("---");

    second = data.state != nullptr ? data.state : "?";
    second += "  ";
    second += String(data.thresholdPct) + "%";
    second += " s";
    second += String(data.scheduleCount);
  } else {
    first = data.clockValid ? clockDate() + " " + clockTime() : String("jam belum di-set");
    second = "WiFi:";
    second += data.wifiOk ? "OK " : ".. ";
    second += "MQTT:";
    second += data.mqttOk ? "OK" : "..";
  }

  drawLine(0, first);
  drawLine(1, second);
}

}  // namespace hw
