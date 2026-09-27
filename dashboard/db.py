"""SQLite access layer.

Port of backend/db.js: same queries and same behavior, SQLite dialect.

Concurrency notes
-----------------
The MQTT worker thread writes on every telemetry tick while the Streamlit thread
reads, so:

* WAL journalling is enabled — one writer can coexist with readers.
* Each thread gets its own connection (sqlite3 connections are not thread-safe).
* The multi-statement operations (manual feed, ack, timeout sweep) run inside an
  explicit ``BEGIN IMMEDIATE`` transaction so they are all-or-nothing.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

import config

# Milliseconds-precision "now", matching the DATETIME(3) semantics of the old
# MySQL schema. Stored as TEXT so the sqlite3 CLI output stays readable.
NOW = "strftime('%Y-%m-%d %H:%M:%f','now')"

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        config.DB_PATH,
        timeout=5.0,
        isolation_level=None,  # autocommit; transactions are explicit below
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")  # off by default in SQLite
    return conn


def connection() -> sqlite3.Connection:
    """Thread-local connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def transaction():
    """Explicit write transaction. Never nest these."""
    conn = connection()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def init_db() -> None:
    """Create the schema if it isn't there yet. Safe to call on every start."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn = connection()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='devices'"
        ).fetchone()
        if exists is None:
            schema = Path(config.SCHEMA_PATH).read_text(encoding="utf-8")
            conn.executescript(schema)
        _initialized = True


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------


def find_device_by_code(device_code: str):
    row = connection().execute(
        "SELECT id, device_code, sensor_full_cm, sensor_empty_cm, low_feed_threshold_pct "
        "FROM devices WHERE device_code = ?",
        (device_code,),
    ).fetchone()
    return dict(row) if row else None


def ensure_device(device_code: str):
    found = find_device_by_code(device_code)
    if found:
        return found
    connection().execute(
        "INSERT OR IGNORE INTO devices (device_code, name) VALUES (?, ?)",
        (device_code, f"Feeder {device_code}"),
    )
    return find_device_by_code(device_code)


def touch_device(device_id: int, online: bool) -> None:
    connection().execute(
        f"UPDATE devices SET is_online = ?, last_seen_at = {NOW}, updated_at = {NOW} "
        "WHERE id = ?",
        (1 if online else 0, device_id),
    )


def list_devices():
    rows = connection().execute(
        "SELECT id, device_code, name, location, is_online, "
        "sensor_full_cm, sensor_empty_cm, low_feed_threshold_pct "
        "FROM devices ORDER BY device_code"
    ).fetchall()
    return [dict(r) for r in rows]


def set_low_feed_threshold(device_id: int, threshold_pct: int) -> None:
    """Keep the alert threshold the app evaluates in step with the device."""
    connection().execute(
        f"UPDATE devices SET low_feed_threshold_pct = ?, updated_at = {NOW} WHERE id = ?",
        (int(threshold_pct), device_id),
    )


def device_status(device_id: int):
    row = connection().execute(
        "SELECT * FROM v_device_status WHERE device_id = ?", (device_id,)
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# telemetry
# ---------------------------------------------------------------------------


def insert_telemetry(*, device_id, distance_cm=None, feed_level_pct=None, state=None):
    cur = connection().execute(
        "INSERT INTO telemetry (device_id, distance_cm, feed_level_pct, state) "
        "VALUES (?, ?, ?, ?)",
        (device_id, distance_cm, feed_level_pct, state),
    )
    return cur.lastrowid


def latest_telemetry(device_id: int):
    row = connection().execute(
        "SELECT distance_cm, feed_level_pct, recorded_at FROM telemetry "
        "WHERE device_id = ? ORDER BY recorded_at DESC, id DESC LIMIT 1",
        (device_id,),
    ).fetchone()
    return dict(row) if row else None


def telemetry_series(device_id: int, since: str):
    rows = connection().execute(
        "SELECT recorded_at, distance_cm, feed_level_pct, state FROM telemetry "
        "WHERE device_id = ? AND recorded_at >= ? ORDER BY recorded_at",
        (device_id, since),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# notifications (anti-spam: one open notification per type per device)
# ---------------------------------------------------------------------------


def has_open_notification(device_id: int, type_: str) -> bool:
    row = connection().execute(
        "SELECT 1 FROM notifications WHERE device_id = ? AND type = ? AND is_read = 0 "
        "LIMIT 1",
        (device_id, type_),
    ).fetchone()
    return row is not None


def insert_notification(
    *, device_id, type_, severity, title, message, feed_level_pct=None
):
    connection().execute(
        "INSERT INTO notifications (device_id, type, severity, title, message, feed_level_pct) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (device_id, type_, severity, title, message, feed_level_pct),
    )


def resolve_notifications(device_id: int, types) -> None:
    if not types:
        return
    placeholders = ",".join("?" for _ in types)
    connection().execute(
        f"UPDATE notifications SET is_read = 1 "
        f"WHERE device_id = ? AND type IN ({placeholders}) AND is_read = 0",
        [device_id, *types],
    )


def list_notifications(device_id: int, unread_only: bool = False):
    sql = (
        "SELECT id, type, severity, title, message, feed_level_pct, is_read, created_at "
        "FROM notifications WHERE device_id = ?"
    )
    params = [device_id]
    if unread_only:
        sql += " AND is_read = 0"
    sql += " ORDER BY created_at DESC, id DESC LIMIT 200"
    return [dict(r) for r in connection().execute(sql, params).fetchall()]


def mark_notification_read(notification_id: int) -> None:
    connection().execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,)
    )


def mark_all_notifications_read(device_id: int) -> None:
    connection().execute(
        "UPDATE notifications SET is_read = 1 WHERE device_id = ? AND is_read = 0",
        (device_id,),
    )


# ---------------------------------------------------------------------------
# commands + feeding_logs
# ---------------------------------------------------------------------------


def insert_command(*, command_id, device_id, type_, payload, conn=None):
    (conn or connection()).execute(
        "INSERT INTO commands (command_id, device_id, type, payload, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (command_id, device_id, type_, payload, "sent"),
    )


def insert_feeding_log(
    *, device_id, command_id, portions, feed_level_before=None, conn=None
):
    cur = (conn or connection()).execute(
        "INSERT INTO feeding_logs "
        "(device_id, command_id, trigger_type, portions, status, feed_level_before_pct) "
        "VALUES (?, ?, 'manual', ?, 'pending', ?)",
        (device_id, command_id, portions, feed_level_before),
    )
    return cur.lastrowid


def apply_ack(*, command_id, ok, message) -> bool:
    conn = connection()
    with transaction():
        cur = conn.execute(
            f"UPDATE commands SET status = ?, result_message = ?, acked_at = {NOW} "
            "WHERE command_id = ?",
            ("success" if ok else "failed", message, command_id),
        )
        if cur.rowcount == 0:
            return False
        conn.execute(
            f"UPDATE feeding_logs SET status = ?, message = ?, completed_at = {NOW} "
            "WHERE command_id = ? AND status = 'pending'",
            ("success" if ok else "failed", message, command_id),
        )
    return True


def attach_feed_level_after(device_id: int, command_id: str) -> None:
    latest = latest_telemetry(device_id)
    if not latest or latest["feed_level_pct"] is None:
        return
    connection().execute(
        "UPDATE feeding_logs SET distance_after_cm = ?, feed_level_after_pct = ? "
        "WHERE command_id = ?",
        (latest["distance_cm"], latest["feed_level_pct"], command_id),
    )


def sweep_timeouts(timeout_sec) -> int:
    """Commands with no ack in time become timeout; their feed logs fail."""
    conn = connection()
    with transaction():
        cur = conn.execute(
            "UPDATE commands SET status = 'timeout' "
            "WHERE status IN ('pending', 'sent') "
            f"AND created_at < strftime('%Y-%m-%d %H:%M:%f','now','-' || ? || ' seconds')",
            (timeout_sec,),
        )
        stale = cur.rowcount
        if stale:
            conn.execute(
                "UPDATE feeding_logs SET status = 'failed', message = 'timeout', "
                f"completed_at = {NOW} "
                "WHERE status = 'pending' AND command_id IN "
                "(SELECT command_id FROM commands WHERE status = 'timeout')"
            )
    return stale


# ---------------------------------------------------------------------------
# schedules
# ---------------------------------------------------------------------------


def list_schedules(device_id: int):
    rows = connection().execute(
        "SELECT id, name, feed_time, portions, is_active, updated_at FROM schedules "
        "WHERE device_id = ? ORDER BY feed_time",
        (device_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def active_schedules(device_id: int):
    rows = connection().execute(
        "SELECT id, name, feed_time, portions FROM schedules "
        "WHERE device_id = ? AND is_active = 1 ORDER BY feed_time",
        (device_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_schedule(*, device_id, name, feed_time, portions) -> int:
    cur = connection().execute(
        "INSERT INTO schedules (device_id, name, feed_time, portions) VALUES (?, ?, ?, ?)",
        (device_id, name, feed_time, portions),
    )
    return cur.lastrowid


def set_schedule_active(schedule_id: int, active: bool) -> None:
    connection().execute(
        f"UPDATE schedules SET is_active = ?, updated_at = {NOW} WHERE id = ?",
        (1 if active else 0, schedule_id),
    )


# ---------------------------------------------------------------------------
# feeding history
# ---------------------------------------------------------------------------


def list_feeding_logs(device_id: int, since: str, until: str):
    rows = connection().execute(
        "SELECT fl.id, fl.requested_at, fl.trigger_type, fl.portions, fl.status, "
        "fl.message, fl.command_id, fl.feed_level_before_pct, fl.feed_level_after_pct, "
        "s.name AS schedule_name "
        "FROM feeding_logs fl LEFT JOIN schedules s ON s.id = fl.schedule_id "
        "WHERE fl.device_id = ? AND fl.requested_at BETWEEN ? AND ? "
        "ORDER BY fl.requested_at DESC, fl.id DESC",
        (device_id, since, until),
    ).fetchall()
    return [dict(r) for r in rows]
