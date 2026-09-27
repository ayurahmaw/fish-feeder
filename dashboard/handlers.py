"""MQTT message handling.

Port of backend/handlers.js — same branches, same alert anti-spam rules.
"""

from __future__ import annotations

import db
from log import log


def _num_or_none(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(payload: dict, *keys):
    """Nullish-coalescing lookup, matching JS ``a ?? b ?? c``."""
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _fmt(value):
    """Render numbers the way JavaScript would (20.0 -> '20')."""
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def compute_pct(device: dict, distance_cm: float):
    """Ultrasonic distance -> percent, clamped 0..100 using per-device calibration."""
    full = _num_or_none(device.get("sensor_full_cm"))
    empty = _num_or_none(device.get("sensor_empty_cm"))
    if full is None or empty is None or empty <= full:
        return None
    return min(100.0, max(0.0, ((empty - distance_cm) / (empty - full)) * 100))


def evaluate_feed_alerts(device: dict, pct):
    """Low/empty feed alerts; one open notification per type, auto-closed when healthy."""
    if pct is None:
        return
    threshold = _num_or_none(device.get("low_feed_threshold_pct")) or 0

    if pct <= 0:
        db.resolve_notifications(device["id"], ["feed_low"])
        if not db.has_open_notification(device["id"], "feed_empty"):
            db.insert_notification(
                device_id=device["id"],
                type_="feed_empty",
                severity="critical",
                title="Pakan habis",
                message="Sisa pakan 0% — segera isi ulang hopper.",
                feed_level_pct=pct,
            )
            log(f"ALERT feed_empty ({device['device_code']})")
    elif pct <= threshold:
        db.resolve_notifications(device["id"], ["feed_empty"])
        if not db.has_open_notification(device["id"], "feed_low"):
            db.insert_notification(
                device_id=device["id"],
                type_="feed_low",
                severity="warning",
                title="Pakan menipis",
                message=f"Sisa pakan {_fmt(pct)}% (threshold {_fmt(threshold)}%).",
                feed_level_pct=pct,
            )
            log(f"ALERT feed_low ({device['device_code']})")
    else:
        db.resolve_notifications(device["id"], ["feed_low", "feed_empty"])


def handle_telemetry(device_code: str, payload: dict) -> None:
    """feeder/<device>/telemetry

    Accepts all the shapes the Node version did:
      {distance_cm, state}      target firmware format (raw distance)
      {feed_level_pct, state}   sim.js today
      {level, state}            Node-RED flow
    """
    device = db.ensure_device(device_code)
    payload = payload or {}

    distance_cm = _num_or_none(
        _first(payload, "distance_cm", "distance", "distanceCm")
    )
    raw_pct = _num_or_none(_first(payload, "feed_level_pct", "level", "feedLevelPct"))
    feed_level_pct = (
        compute_pct(device, distance_cm) if distance_cm is not None else raw_pct
    )
    state = payload.get("state")

    db.insert_telemetry(
        device_id=device["id"],
        distance_cm=distance_cm,
        feed_level_pct=feed_level_pct,
        state=state,
    )
    db.touch_device(device["id"], True)
    evaluate_feed_alerts(device, feed_level_pct)

    log(
        f"telemetry {device_code}: distance={_fmt(distance_cm)}cm "
        f"level={_fmt(feed_level_pct)}% state={state or '-'}"
    )


def handle_ack(device_code: str, payload: dict) -> None:
    """feeder/<device>/ack  {command_id, result, message}"""
    device = db.ensure_device(device_code)
    payload = payload or {}

    command_id = _first(payload, "command_id", "commandId")
    if not command_id:
        log(f"ack dari {device_code} tanpa command_id — diabaikan")
        return

    ok = str(_first(payload, "result") or "").lower() == "ok"
    message = _first(payload, "message", "result") or ""
    message = str(message)

    if not db.apply_ack(command_id=str(command_id), ok=ok, message=message):
        log(f"ack command_id tidak dikenal: {command_id}")
        return

    if ok:
        db.attach_feed_level_after(device["id"], str(command_id))
        log(f"command {command_id} -> success ({message})")
    else:
        db.insert_notification(
            device_id=device["id"],
            type_="feed_failed",
            severity="critical",
            title="Pemberian pakan gagal",
            message=message,
        )
        log(f"command {command_id} -> FAILED ({message})")


def handle_status(device_code: str, payload) -> None:
    """feeder/<device>/status  ("online" / "offline", retained LWT/birth)"""
    device = db.ensure_device(device_code)

    if isinstance(payload, str):
        status = payload.strip()
    else:
        payload = payload or {}
        raw = _first(payload, "status", "state")
        status = "" if raw is None else str(raw).strip()
    if not status:
        return

    online = status == "online"
    db.touch_device(device["id"], online)

    if online:
        db.resolve_notifications(device["id"], ["device_offline"])
        log(f"{device_code} online")
    elif status == "offline":
        if not db.has_open_notification(device["id"], "device_offline"):
            db.insert_notification(
                device_id=device["id"],
                type_="device_offline",
                severity="warning",
                title="Perangkat offline",
                message=f"{device_code} tidak merespons (LWT offline).",
            )
            log(f"ALERT device_offline ({device_code})")
