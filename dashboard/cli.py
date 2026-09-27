#!/usr/bin/env python
"""Kirim perintah ke feeder dari command line.

Pengganti backend/send-command.js. Perintah masuk ke tabel `commands`
(+ `feeding_logs` untuk manual_feed) lalu dipublish ke MQTT.

Pemakaian:
    python cli.py <type> [device_code] ['{payload json}']

Contoh:
    pipenv run python cli.py manual_feed feeder01 '{"portions":2}'
    pipenv run python cli.py get_state feeder01
    pipenv run python cli.py set_threshold feeder01 '{"threshold_pct":25}'

Catatan: aplikasi Streamlit harus sedang berjalan — dialah yang menjalankan
broker MQTT dan memproses ack.
"""

from __future__ import annotations

import json
import os
import sys
import threading

import paho.mqtt.client as mqtt

import config
import db
from commands import send_command


def main(argv) -> int:
    type_ = argv[0] if len(argv) > 0 else "manual_feed"
    device_code = argv[1] if len(argv) > 1 else "feeder01"

    payload = {}
    if len(argv) > 2 and argv[2]:
        try:
            payload = json.loads(argv[2])
        except json.JSONDecodeError:
            print("payload bukan JSON valid, contoh: '{\"portions\":2}'", file=sys.stderr)
            return 1

    db.init_db()

    ready = threading.Event()
    host, port = config.mqtt_host_port()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"feeder-cli-{os.getpid()}"
    )
    client.on_connect = lambda *args, **kwargs: ready.set()

    try:
        client.connect(host, port, keepalive=60)
    except Exception as exc:
        print(f"tidak bisa terhubung ke broker {config.MQTT_URL}: {exc}", file=sys.stderr)
        return 1

    client.loop_start()
    try:
        if not ready.wait(5):
            print(f"broker {config.MQTT_URL} tidak merespons", file=sys.stderr)
            return 1

        result = send_command(client, config.TOPIC_PREFIX, device_code, type_, payload)
        print(f"terkirim: {type_} -> {device_code} (command_id={result['command_id']})")
        if type_ == "manual_feed":
            print("feeding_logs dibuat berstatus pending, menunggu ack...")
    except Exception as exc:
        print(f"gagal: {exc}", file=sys.stderr)
        return 1
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
