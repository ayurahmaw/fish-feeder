"""Feeder monitoring + control dashboard.

One Streamlit app that hosts the MQTT broker, the SQLite database, the
ingestion worker and this UI.

    pipenv run streamlit run app.py      # -> http://localhost:8501
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import config
import db
from commands import send_command
from runtime import get_runtime

st.set_page_config(page_title="Feeder Monitor", page_icon="🐟", layout="wide")

runtime = get_runtime()

REFRESH = "2s"
SEVERITY_ICON = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


# --------------------------------------------------------------------------- #
# cached reads — UI thread only (the worker threads call db.* directly)
# --------------------------------------------------------------------------- #
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


@st.cache_data(ttl=5)
def feeding_logs(device_id: int, since: str, until: str):
    return db.list_feeding_logs(device_id, since, until)


def clear_reads():
    for reader in (
        devices,
        status_of,
        telemetry,
        notifications,
        schedules,
        feeding_logs,
    ):
        reader.clear()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def stamp(moment: datetime) -> str:
    """Timestamp string matching the format stored in SQLite."""
    return moment.strftime("%Y-%m-%d %H:%M:%S.") + f"{moment.microsecond // 1000:03d}"


def num(value, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


# --------------------------------------------------------------------------- #
# sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("🐟 Feeder Monitor")

    device_list = devices()
    if not device_list:
        st.error("Belum ada device di database.")
        st.stop()

    chosen = st.selectbox("Device", [d["device_code"] for d in device_list])
    device = next(d for d in device_list if d["device_code"] == chosen)

    st.divider()
    st.caption("Runtime")
    st.write(f"**Broker:** {runtime.broker_label}")
    st.write(f"**Worker:** {'terhubung ✅' if runtime.worker.connected else 'terputus ⏳'}")
    st.write(f"**Database:** `{config.DB_PATH}`")
    st.write(f"**Timeout ack:** {config.COMMAND_TIMEOUT_SEC} s")

    if st.button("Muat ulang data"):
        clear_reads()
        st.rerun()


# --------------------------------------------------------------------------- #
# tabs
# --------------------------------------------------------------------------- #
tab_status, tab_live, tab_alerts, tab_history, tab_sched, tab_control = st.tabs(
    ["Status", "Live", "Alerts", "History", "Schedules", "Control"]
)


@st.fragment(run_every=REFRESH)
def render_status(device):
    s = status_of(device["id"])
    if s is None or s["measured_at"] is None:
        st.info("Belum ada telemetry untuk device ini. Jalankan `node sim.js`.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sisa pakan", "—" if s["feed_level_pct"] is None else f"{s['feed_level_pct']:.1f}%")
    c2.metric("Jarak sensor", "—" if s["distance_cm"] is None else f"{s['distance_cm']:.1f} cm")
    c3.metric("State", s["state"] or "—")
    c4.metric("Online", "ya" if s["is_online"] else "tidak")

    if s["is_empty"]:
        st.error("🔴 Pakan habis (0%) — segera isi ulang hopper.")
    elif s["is_low"]:
        st.warning(f"🟠 Pakan menipis (≤ {s['low_feed_threshold_pct']}%).")
    else:
        st.success("🟢 Level pakan sehat.")

    st.caption(
        f"Kalibrasi penuh {s['sensor_full_cm']:.1f} cm · kosong {s['sensor_empty_cm']:.1f} cm · "
        f"threshold {s['low_feed_threshold_pct']}% · "
        f"terakhir dilihat {s['last_seen_at'] or '—'} · diukur {s['measured_at']}"
    )


@st.fragment(run_every=REFRESH)
def render_live(device):
    hours = st.radio(
        "Rentang", [1, 6, 24], index=0, horizontal=True, format_func=lambda h: f"{h} jam"
    )
    rows = telemetry(device["id"], stamp(datetime.now() - timedelta(hours=hours)))

    if rows:
        frame = pd.DataFrame(rows)
        frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])
        frame = frame.set_index("recorded_at")
        series = frame[["feed_level_pct"]].rename(columns={"feed_level_pct": "sisa pakan (%)"})
        if frame["distance_cm"].notna().any():
            series["jarak (cm)"] = frame["distance_cm"]
        st.line_chart(series)
        st.caption(f"{len(frame)} titik telemetry dalam {hours} jam terakhir.")
    else:
        st.info("Belum ada telemetry pada rentang ini.")

    st.subheader("Pesan MQTT terbaru")
    tail = runtime.worker.tail_snapshot()
    if tail:
        st.dataframe(
            pd.DataFrame(list(reversed(tail))), width="stretch", height=260, hide_index=True
        )
    else:
        st.caption("Belum ada pesan masuk.")


def render_alerts(device):
    left, right = st.columns([3, 1])
    unread_only = left.toggle("Hanya yang belum dibaca", value=False)
    if right.button("Tandai semua dibaca"):
        db.mark_all_notifications_read(device["id"])
        clear_reads()
        st.rerun()

    rows = notifications(device["id"], unread_only)
    if not rows:
        st.success("Tidak ada notifikasi." if not unread_only else "Tidak ada notifikasi baru.")
        return

    for note in rows[:30]:
        with st.container(border=True):
            body, action = st.columns([6, 1])
            body.markdown(
                f"{SEVERITY_ICON.get(note['severity'], '•')} "
                f"**{note['title'] or note['type']}** · `{note['type']}`  \n"
                f"{note['message']}  \n"
                f"<small>{note['created_at']} · level {num(note['feed_level_pct'])}%</small>",
                unsafe_allow_html=True,
            )
            if note["is_read"]:
                action.caption("dibaca")
            elif action.button("Baca", key=f"read-{note['id']}"):
                db.mark_notification_read(note["id"])
                clear_reads()
                st.rerun()

    if len(rows) > 30:
        st.caption(f"Menampilkan 30 dari {len(rows)} notifikasi.")


def render_history(device):
    days = st.selectbox("Periode", [1, 7, 30], index=1, format_func=lambda d: f"{d} hari")
    now = datetime.now()
    rows = feeding_logs(device["id"], stamp(now - timedelta(days=days)), stamp(now))

    if not rows:
        st.info("Belum ada riwayat pemberian pakan pada periode ini.")
        return

    frame = pd.DataFrame(rows)[
        [
            "requested_at",
            "trigger_type",
            "schedule_name",
            "portions",
            "status",
            "message",
            "feed_level_before_pct",
            "feed_level_after_pct",
        ]
    ].rename(
        columns={
            "requested_at": "waktu",
            "trigger_type": "trigger",
            "schedule_name": "jadwal",
            "portions": "porsi",
            "status": "status",
            "message": "pesan",
            "feed_level_before_pct": "level sebelum (%)",
            "feed_level_after_pct": "level sesudah (%)",
        }
    )
    st.dataframe(frame, width="stretch", hide_index=True)

    success = sum(1 for r in rows if r["status"] == "success")
    st.caption(
        f"{len(rows)} catatan · {success} sukses · "
        f"{len(rows) - success} gagal/tertunda"
    )


def render_schedules(device):
    rows = schedules(device["id"])

    if rows:
        frame = pd.DataFrame(rows)[
            ["id", "name", "feed_time", "portions", "is_active", "updated_at"]
        ].rename(
            columns={
                "id": "id",
                "name": "nama",
                "feed_time": "jam",
                "portions": "porsi",
                "is_active": "aktif",
                "updated_at": "diubah",
            }
        )
        st.dataframe(frame, width="stretch", hide_index=True)
    else:
        st.info("Belum ada jadwal.")

    st.subheader("Tambah jadwal")
    with st.form("add-schedule", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Nama", value="Pakan Malam")
        clock = c2.time_input("Jam", value=datetime.strptime("21:00", "%H:%M").time())
        portions = c3.number_input("Porsi", min_value=1, max_value=50, value=1, step=1)
        if st.form_submit_button("Simpan"):
            db.insert_schedule(
                device_id=device["id"],
                name=name,
                feed_time=clock.strftime("%H:%M:%S"),
                portions=int(portions),
            )
            clear_reads()
            st.rerun()

    if rows:
        st.subheader("Aktif / nonaktif")
        for item in rows:
            label, action = st.columns([6, 1])
            state = "aktif" if item["is_active"] else "nonaktif"
            label.write(
                f"**{item['name']}** · {item['feed_time'][:5]} · {item['portions']} porsi · {state}"
            )
            if action.button(
                "Nonaktifkan" if item["is_active"] else "Aktifkan", key=f"tog-{item['id']}"
            ):
                db.set_schedule_active(item["id"], not item["is_active"])
                clear_reads()
                st.rerun()

        st.divider()
        if st.button("Kirim jadwal aktif ke device (set_schedule)"):
            result = send_command(
                runtime.worker.client,
                config.TOPIC_PREFIX,
                device["device_code"],
                "set_schedule",
                {"schedules": db.active_schedules(device["id"])},
            )
            st.success(f"Terkirim · command_id={result['command_id']}")


def render_control(device):
    st.subheader("Pakan manual")
    c1, c2 = st.columns([1, 2])
    portions = c1.number_input(
        "Porsi", min_value=1, max_value=50, value=2, step=1, key="manual-portions"
    )
    if c2.button("Beri pakan sekarang", type="primary"):
        result = send_command(
            runtime.worker.client,
            config.TOPIC_PREFIX,
            device["device_code"],
            "manual_feed",
            {"portions": int(portions)},
        )
        clear_reads()
        st.success(
            f"Perintah terkirim · command_id={result['command_id']} · menunggu ack "
            f"(timeout {config.COMMAND_TIMEOUT_SEC}s)."
        )

    st.divider()
    st.subheader("Perintah lain")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.caption("Minta state lengkap dari device")
        if st.button("get_state"):
            result = send_command(
                runtime.worker.client,
                config.TOPIC_PREFIX,
                device["device_code"],
                "get_state",
                {},
            )
            st.info(f"command_id={result['command_id']}")

    with c2:
        threshold = st.number_input(
            "Threshold pakan menipis (%)",
            min_value=0,
            max_value=100,
            value=int(device["low_feed_threshold_pct"]),
            step=1,
            key="threshold",
        )
        st.caption("Mengubah ambang alert di aplikasi **dan** mengirim ke device")
        if st.button("set_threshold"):
            db.set_low_feed_threshold(device["id"], int(threshold))
            result = send_command(
                runtime.worker.client,
                config.TOPIC_PREFIX,
                device["device_code"],
                "set_threshold",
                {"threshold_pct": int(threshold)},
            )
            clear_reads()
            st.info(f"command_id={result['command_id']} · threshold={int(threshold)}%")

    with c3:
        when = st.date_input("Tanggal", value=datetime.now().date(), key="rtc-date")
        clock = st.time_input(
            "Jam", value=datetime.now().time().replace(microsecond=0), key="rtc-time"
        )
        if st.button("set_rtc"):
            result = send_command(
                runtime.worker.client,
                config.TOPIC_PREFIX,
                device["device_code"],
                "set_rtc",
                {"datetime": datetime.combine(when, clock).strftime("%Y-%m-%dT%H:%M:%S")},
            )
            st.info(f"command_id={result['command_id']}")


with tab_status:
    render_status(device)
with tab_live:
    render_live(device)
with tab_alerts:
    render_alerts(device)
with tab_history:
    render_history(device)
with tab_sched:
    render_schedules(device)
with tab_control:
    render_control(device)
