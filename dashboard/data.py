"""Cached read helpers for the Streamlit UI.

The MQTT worker writes through ``db`` directly; this module only wraps the
queries the pages consume so a short TTL keeps the 2-second refresh cheap.
"""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

import db


def sql_now() -> datetime:
    """UTC now, used for SQL time filters (SQLite stamps every row in UTC)."""
    return datetime.now(timezone.utc)


def sql_stamp(moment: datetime) -> str:
    """Timestamp string matching the format stored in SQLite."""
    return moment.strftime("%Y-%m-%d %H:%M:%S.") + f"{moment.microsecond // 1000:03d}"


@st.cache_data(ttl=2)
def devices():
    return db.list_devices()


@st.cache_data(ttl=2)
def status_of(device_id: int):
    return db.device_status(device_id)


@st.cache_data(ttl=2)
def telemetry(device_id: int, since: str):
    return db.telemetry_series(device_id, since)


@st.cache_data(ttl=2)
def notifications(device_id: int, unread_only: bool):
    return db.list_notifications(device_id, unread_only)


@st.cache_data(ttl=2)
def schedules(device_id: int):
    return db.list_schedules(device_id)


@st.cache_data(ttl=2)
def recent_commands(device_id: int, limit: int = 10):
    return db.list_commands(device_id, limit)


@st.cache_data(ttl=2)
def latest_feeding_log(device_id: int):
    return db.latest_feeding_log(device_id)


@st.cache_data(ttl=5)
def feeding_logs(device_id: int, since: str, until: str):
    return db.list_feeding_logs(device_id, since, until)


def clear_reads() -> None:
    for reader in (
        devices,
        status_of,
        telemetry,
        notifications,
        schedules,
        recent_commands,
        latest_feeding_log,
        feeding_logs,
    ):
        reader.clear()
