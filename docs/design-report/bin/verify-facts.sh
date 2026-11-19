#!/usr/bin/env bash
# Penjaga konsistensi dokumen.
#
# 1. facts.tex harus cocok dengan nilai di firmware/esp32_feeder/config.h
# 2. angka kalibrasi lama (5.00 / 25.00 / 5/25) tidak boleh muncul lagi
# 3. setiap \mmdfig{...} dan \tikzfig{...} harus punya berkas hasil render
# 4. setiap sumber .mmd harus punya header "%% title:"
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
CONFIG_H="$ROOT/firmware/esp32_feeder/config.h"
FACTS="preamble/facts.tex"

errors=0
err() { printf '  GAGAL  %s\n' "$*" >&2; errors=$((errors + 1)); }
ok()  { printf '  ok     %s\n' "$*"; }

echo "1. facts.tex vs config.h"
if [ ! -f "$CONFIG_H" ]; then
  err "config.h tidak ditemukan: $CONFIG_H"
else
  define_val() {
    grep -E "^#define[[:space:]]+$1[[:space:]]" "$CONFIG_H" | head -1 \
      | sed -E "s/^#define[[:space:]]+$1[[:space:]]+//" \
      | sed -E 's/[[:space:]]*(\/\/|$).*//' \
      | sed -E 's/^"(.*)"$/\1/' \
      | sed -E 's/[uUlLfF]+$//'
  }
  macro_val() {
    sed -nE "s/^[[:space:]]*\\\\newcommand\{\\\\$1\}\{([^}]*)\}.*/\1/p" "$FACTS" | head -1
  }

  # pasangan: MACRO_CONFIG MACRO_TEX
  PAIRS="
    HOPPER_FULL_CM:HopperFull
    HOPPER_EMPTY_CM:HopperEmpty
    PIN_SERVO:PinServo
    PIN_TRIG:PinTrig
    PIN_ECHO:PinEcho
    PIN_SDA:PinSda
    PIN_SCL:PinScl
    PORTION_OPEN_MS:PortionOpenMs
    SERVO_SETTLE_MS:SettleMs
    PORTION_GAP_MS:GapMs
    TELEMETRY_INTERVAL_MS:TelemetryMs
    SENSOR_INTERVAL_MS:SensorMs
    DISPLAY_INTERVAL_MS:DisplayMs
    DISPLAY_PAGE_MS:PageMs
    MQTT_RETRY_MS:RetryMs
    MAX_SCHEDULES:MaxSchedules
    SCHEDULE_WINDOW_SEC:WindowS
    MQTT_BUFFER_SIZE:MqttBuffer
    COMMAND_QUEUE_SIZE:CmdQueue
    FW_VERSION:FwVersion
    TOPIC_PREFIX:TopicPrefix
    NVS_NAMESPACE:NvsNamespace
  "

  for pair in $PAIRS; do
    cfg="${pair%%:*}"
    tex="${pair##*:}"
    a="$(define_val "$cfg")"
    b="$(macro_val "$tex")"
    if [ -z "$a" ] || [ -z "$b" ]; then
      err "$cfg / \\$tex tidak terbaca ($a vs $b)"
    elif [ "$a" != "$b" ]; then
      err "$cfg=$a di config.h tetapi \\$tex=$b di facts.tex"
    else
      ok "$cfg = $a"
    fi
  done
fi

echo "2. angka kalibrasi lama"
# Batas kata ketat supaya koordinat TikZ (15.00) dan lebar kolom (5.0cm) tidak ikut tertangkap.
LEGACY="$(grep -rnE '(^|[^0-9.])25\.00([^0-9]|$)|(^|[^0-9.])5\.00([^0-9]|$)|(^|[^0-9])5/25([^0-9]|$)' \
  --include='*.tex' --include='*.mmd' . 2>/dev/null \
  | grep -vE 'p\{[0-9.]+cm|cm}$|\([-0-9.]+, *[-0-9.]+\)' || true)"
if [ -n "$LEGACY" ]; then
  printf '%s\n' "$LEGACY" | sed 's/^/         /' >&2
  err "masih ada 5.00/25.00/5-25 di sumber dokumen (harus 3.0/17.0)"
else
  ok "tidak ada sisa 5.00 / 25.00 / 5-25"
fi

echo "3. rujukan gambar"
missing=0
for ref in $(grep -rhoE '\\mmdfig\{[^}]+\}' chapters 2>/dev/null | sed -E 's/.*\{(.*)\}/\1/' | sort -u); do
  if [ -f "assets/diagrams/pdf/$ref.pdf" ]; then
    ok "mmd $ref"
  else
    err "assets/diagrams/pdf/$ref.pdf belum ada"
  fi
done
for ref in $(grep -rhoE '\\tikzfig\{[^}]+\}' chapters 2>/dev/null | sed -E 's/.*\{(.*)\}/\1/' | sort -u); do
  if [ -f "assets/tikz/build/$ref.pdf" ]; then
    ok "tikz $ref"
  else
    err "assets/tikz/build/$ref.pdf belum ada"
  fi
done

echo "4. header sumber mermaid"
for src in assets/diagrams/src/*.mmd; do
  [ -e "$src" ] || continue
  if head -1 "$src" | grep -q '^%% title:'; then
    ok "$(basename "$src")"
  else
    err "$(basename "$src") tidak diawali '%% title:'"
  fi
done

echo
if [ "$errors" -gt 0 ]; then
  printf '%d masalah ditemukan.\n' "$errors" >&2
  exit 1
fi
echo "Semua pemeriksaan lolos."
