"""Outbound commands.

Port of backend/commands.js. The ordering is the whole point: the ``commands``
row and the ``feeding_logs`` row are written *before* the message is published,
so the ack that comes back can always be correlated by ``command_id``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import db
from log import log_err


def _portions(value) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1
    return int(number) if number > 0 else 1


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def send_command(client, topic_prefix: str, device_code: str, type_: str, payload=None):
    """Create the DB rows, then publish to feeder/<device>/command (QoS 1)."""
    payload = payload or {}
    device = db.ensure_device(device_code)
    command_id = f"cmd-{uuid4()}"

    feed_log_id = None
    with db.transaction() as conn:
        db.insert_command(
            command_id=command_id,
            device_id=device["id"],
            type_=type_,
            payload=json.dumps(payload),
            conn=conn,
        )
        if type_ == "manual_feed":
            latest = db.latest_telemetry(device["id"])
            feed_log_id = db.insert_feeding_log(
                device_id=device["id"],
                command_id=command_id,
                portions=_portions(payload.get("portions")),
                feed_level_before=(latest or {}).get("feed_level_pct"),
                conn=conn,
            )

    message = {
        "command_id": command_id,
        "type": type_,
        "payload": payload,
        "timestamp": _now_iso(),
    }
    info = client.publish(
        f"{topic_prefix}/{device_code}/command", json.dumps(message), qos=1
    )
    try:
        info.wait_for_publish(timeout=5)
    except Exception as exc:  # publish failures must not lose the DB record
        log_err(f"publish {command_id} tidak terkonfirmasi: {exc}")

    return {"command_id": command_id, "feed_log_id": feed_log_id}
