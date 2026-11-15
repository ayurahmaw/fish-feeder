"""Bahasa Indonesia / English copy for the dashboard.

Every user-facing string lives here. Protocol values (device codes, MQTT topics,
command ids, enum values) are intentionally left untranslated.
"""

from __future__ import annotations

import streamlit as st

LOCALES = ("id", "en")


def locale() -> str:
    """Current locale, defaulting to Indonesian."""
    value = st.session_state.get("locale") if hasattr(st, "session_state") else None
    return value if value in LOCALES else "id"


def _pick(entry: dict, *args) -> str:
    value = entry.get(locale()) or entry.get("id") or ""
    return value.format(*args) if args else value


def t(key: str, **fmt) -> str:
    """Translate ``key`` and interpolate ``{placeholders}``."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(locale()) or entry.get("id") or key
    return text.format(**fmt) if fmt else text


PAGE_COPY = {
    "status": {
        "id": {"title": "Status", "description": "Ringkasan kondisi feeder saat ini."},
        "en": {"title": "Overview", "description": "A summary of your feeder right now."},
    },
    "live": {
        "id": {"title": "Live", "description": "Telemetri sensor dan lalu lintas MQTT."},
        "en": {"title": "Live", "description": "Sensor telemetry and MQTT traffic."},
    },
    "alerts": {
        "id": {"title": "Notifikasi", "description": "Peringatan yang memerlukan perhatian."},
        "en": {"title": "Alerts", "description": "Warnings that may need your attention."},
    },
    "history": {
        "id": {"title": "Riwayat", "description": "Jejak lengkap aktivitas pemberian pakan."},
        "en": {"title": "History", "description": "A complete record of feeding activity."},
    },
    "schedules": {
        "id": {"title": "Jadwal", "description": "Atur waktu pemberian pakan otomatis harian."},
        "en": {"title": "Schedules", "description": "Manage daily automatic feeding times."},
    },
    "control": {
        "id": {"title": "Kontrol", "description": "Kirim perintah langsung ke perangkat."},
        "en": {"title": "Control", "description": "Send direct commands to the device."},
    },
}


NAV_LABELS = {
    "status": {"id": "Status", "en": "Overview"},
    "live": {"id": "Live", "en": "Live"},
    "alerts": {"id": "Notifikasi", "en": "Alerts"},
    "history": {"id": "Riwayat", "en": "History"},
    "schedules": {"id": "Jadwal", "en": "Schedules"},
    "control": {"id": "Kontrol", "en": "Control"},
}


STATE_LABELS = {
    "idle": {"id": "Siaga", "en": "Idle"},
    "feeding": {"id": "Memberi pakan", "en": "Feeding"},
    "error": {"id": "Gangguan", "en": "Error"},
}

STATUS_LABELS = {
    "pending": {"id": "Menunggu", "en": "Pending"},
    "sent": {"id": "Terkirim", "en": "Sent"},
    "success": {"id": "Berhasil", "en": "Success"},
    "failed": {"id": "Gagal", "en": "Failed"},
    "timeout": {"id": "Timeout", "en": "Timeout"},
}


def state_label(value: str | None) -> str:
    return _pick(STATE_LABELS.get(value or "", {})) or (value or "—")


def status_label(value: str | None) -> str:
    return _pick(STATUS_LABELS.get(value or "", {})) or (value or "—")


STRINGS: dict[str, dict[str, str]] = {
    # shell / sidebar
    "device": {"id": "Perangkat", "en": "Device"},
    "select_device": {"id": "Pilih perangkat", "en": "Select device"},
    "language": {"id": "Bahasa", "en": "Language"},
    "reload": {"id": "Muat ulang data", "en": "Reload data"},
    "refresh": {"id": "Perbarui", "en": "Refresh"},
    "updated": {"id": "Diperbarui", "en": "Updated"},
    "refreshed_toast": {"id": "Data berhasil diperbarui", "en": "Data refreshed"},
    "online": {"id": "Perangkat online", "en": "Device online"},
    "offline": {"id": "Perangkat offline", "en": "Device offline"},
    "system_status": {"id": "Status sistem", "en": "System status"},
    "healthy": {"id": "Normal", "en": "Healthy"},
    "broker": {"id": "Broker MQTT", "en": "MQTT broker"},
    "broker_embedded": {"id": "Tertanam", "en": "Embedded"},
    "broker_existing": {"id": "Broker lokal", "en": "Local broker"},
    "broker_external": {"id": "Eksternal", "en": "External"},
    "worker": {"id": "Worker", "en": "Worker"},
    "database": {"id": "SQLite", "en": "SQLite"},
    "connected": {"id": "Terhubung", "en": "Connected"},
    "disconnected": {"id": "Terputus", "en": "Disconnected"},
    "ready": {"id": "Siap", "en": "Ready"},
    "ack_timeout": {"id": "Timeout ack", "en": "ACK timeout"},
    "local_footer": {"id": "Jaringan lokal · v1.1", "en": "Local network · v1.1"},
    "no_device": {"id": "Belum ada device di database.", "en": "No device in the database yet."},
    "data_backup": {"id": "Data & backup", "en": "Data & backup"},
    "data_backup_sub": {
        "id": "Penyimpanan Cloud bersifat sementara. Unduh cadangan sebelum "
              "redeploy, unggah untuk memulihkan riwayat.",
        "en": "Cloud storage is ephemeral. Download a backup before redeploying; "
              "upload one to restore history.",
    },
    "download_db": {"id": "Unduh database", "en": "Download database"},
    "restore_db": {"id": "Pulihkan database", "en": "Restore database"},
    "restore_apply": {"id": "Terapkan restore", "en": "Apply restore"},
    "restore_ok": {"id": "Database berhasil dipulihkan", "en": "Database restored"},
    "restore_failed": {"id": "Gagal memulihkan: {err}", "en": "Restore failed: {err}"},
    "backup_failed": {"id": "Gagal membuat cadangan: {err}", "en": "Backup failed: {err}"},

    # shared
    "portions": {"id": "porsi", "en": "portions"},
    "cancel": {"id": "Batal", "en": "Cancel"},
    "today": {"id": "HARI INI", "en": "TODAY"},

    # status page
    "welcome_eyebrow": {"id": "SELAMAT DATANG KEMBALI", "en": "WELCOME BACK"},
    "welcome_ok": {"id": "Kolam Anda dalam kondisi baik.", "en": "Your pond is doing well."},
    "welcome_low": {"id": "Pakan mulai menipis.", "en": "Feed is running low."},
    "welcome_empty": {"id": "Pakan habis — isi hopper.", "en": "Feed is empty — refill the hopper."},
    "welcome_sub": {
        "id": "Semua sistem terhubung. Pemberian pakan berikutnya pukul {time}.",
        "en": "All systems are connected. The next feeding is at {time}.",
    },
    "welcome_no_schedule": {
        "id": "Tidak ada jadwal aktif saat ini.",
        "en": "There are no active schedules right now.",
    },
    "feed_remaining": {"id": "SISA PAKAN", "en": "FEED REMAINING"},
    "hopper_level": {"id": "Sisa pakan", "en": "Feed remaining"},
    "badge_healthy": {"id": "Baik", "en": "Good"},
    "badge_low": {"id": "Hampir habis", "en": "Running low"},
    "badge_empty": {"id": "Habis", "en": "Empty"},
    "days_left": {"id": "Cukup untuk sekitar {days} hari", "en": "Enough for about {days} days"},
    "days_left_unknown": {"id": "Estimasi belum tersedia", "en": "Estimate not available yet"},
    "alert_threshold": {"id": "Ambang notifikasi", "en": "Alert threshold"},
    "sensor_distance": {"id": "Jarak sensor", "en": "Sensor distance"},
    "device_state": {"id": "Status perangkat", "en": "Device state"},
    "connection": {"id": "Koneksi", "en": "Connection"},
    "last_seen": {"id": "Terakhir terlihat", "en": "Last seen"},
    "normal_range": {"id": "Rentang normal", "en": "Normal range"},
    "servo_ready": {"id": "Servo siap", "en": "Servo ready"},
    "signal_stable": {"id": "Sinyal stabil", "en": "Signal stable"},
    "latest_telemetry": {"id": "Telemetri terbaru", "en": "Latest telemetry"},
    "seconds_short": {"id": "dtk", "en": "sec"},
    "next_schedule": {"id": "Jadwal berikutnya", "en": "Next schedule"},
    "manage": {"id": "Kelola", "en": "Manage"},
    "in_duration": {"id": "Dalam {duration}", "en": "In {duration}"},
    "no_active_schedule": {"id": "Belum ada jadwal aktif.", "en": "No active schedules yet."},
    "latest_activity": {"id": "AKTIVITAS TERAKHIR", "en": "LATEST ACTIVITY"},
    "feeding_event": {"id": "Pemberian pakan", "en": "Feeding event"},
    "before": {"id": "Sebelum", "en": "Before"},
    "after": {"id": "Sesudah", "en": "After"},
    "no_feeding_yet": {"id": "Belum ada aktivitas pakan.", "en": "No feeding activity yet."},
    "quick_actions": {"id": "Aksi cepat", "en": "Quick actions"},
    "quick_actions_sub": {
        "id": "Kontrol paling sering digunakan.",
        "en": "Your most frequently used controls.",
    },
    "feed_now": {"id": "Beri pakan sekarang", "en": "Feed now"},
    "request_state": {"id": "Minta status", "en": "Request state"},
    "no_telemetry": {
        "id": "Belum ada telemetry untuk device ini. Jalankan `node sim.js`.",
        "en": "No telemetry for this device yet. Run `node sim.js`.",
    },
    "scheduled_ok": {"id": "Jadwal pagi selesai", "en": "Schedule completed"},

    # live page
    "feed_level": {"id": "Level pakan", "en": "Feed level"},
    "live_sub": {"id": "Telemetri sensor terbaru", "en": "Latest sensor telemetry"},
    "range": {"id": "Rentang waktu", "en": "Time range"},
    "hour_short": {"id": "{n}j", "en": "{n}h"},
    "current": {"id": "Saat ini", "en": "Current"},
    "distance": {"id": "Jarak", "en": "Distance"},
    "refresh_2s": {"id": "Pembaruan 2 detik", "en": "2-second refresh"},
    "legend_remaining": {"id": "Sisa pakan", "en": "Feed remaining"},
    "legend_threshold": {"id": "Ambang {pct}%", "en": "{pct}% threshold"},
    "mqtt_recent": {"id": "Pesan MQTT terbaru", "en": "Recent MQTT messages"},
    "mqtt_sub": {
        "id": "Aliran data perangkat secara langsung",
        "en": "Live device data stream",
    },
    "all_topics": {"id": "Semua topik", "en": "All topics"},
    "pause": {"id": "Jeda", "en": "Pause"},
    "resume": {"id": "Lanjutkan", "en": "Resume"},
    "paused_notice": {
        "id": "Tampilan pesan dijeda. Data perangkat tetap diterima.",
        "en": "Message display is paused. Device data is still being received.",
    },
    "time_col": {"id": "Waktu", "en": "Time"},
    "type_col": {"id": "Tipe", "en": "Type"},
    "topic_col": {"id": "Topic", "en": "Topic"},
    "payload_col": {"id": "Payload", "en": "Payload"},
    "no_messages": {"id": "Belum ada pesan masuk.", "en": "No messages yet."},
    "no_telemetry_range": {
        "id": "Belum ada telemetry pada rentang ini.",
        "en": "No telemetry in this range.",
    },
    "telemetry_points": {
        "id": "{n} titik telemetry dalam {h} jam terakhir.",
        "en": "{n} telemetry points in the last {h} hours.",
    },

    # alerts page
    "unread": {"id": "Belum dibaca", "en": "Unread"},
    "warnings": {"id": "Peringatan", "en": "Warnings"},
    "critical": {"id": "Kritis", "en": "Critical"},
    "all": {"id": "Semua", "en": "All"},
    "mark_all_read": {"id": "Tandai semua dibaca", "en": "Mark all as read"},
    "mark_read": {"id": "Tandai dibaca", "en": "Mark read"},
    "read": {"id": "Dibaca", "en": "Read"},
    "all_clear": {"id": "Semua beres", "en": "All clear"},
    "no_alerts_filter": {
        "id": "Tidak ada notifikasi untuk filter ini.",
        "en": "There are no alerts for this filter.",
    },
    "showing_n": {
        "id": "Menampilkan {n} dari {total} notifikasi.",
        "en": "Showing {n} of {total} alerts.",
    },

    # history page
    "day": {"id": "hari", "en": "day"},
    "days": {"id": "hari", "en": "days"},
    "all_statuses": {"id": "Semua status", "en": "All statuses"},
    "total_events": {"id": "Total aktivitas", "en": "Total events"},
    "successful": {"id": "Berhasil", "en": "Successful"},
    "failed_timeout": {"id": "Gagal / timeout", "en": "Failed / timeout"},
    "total_portions": {"id": "Total porsi", "en": "Total portions"},
    "feeding_history": {"id": "Riwayat pemberian pakan", "en": "Feeding history"},
    "history_sub": {
        "id": "Aktivitas {days} hari terakhir",
        "en": "Activity from the last {days} days",
    },
    "trigger_col": {"id": "Pemicu", "en": "Trigger"},
    "manual": {"id": "Manual", "en": "Manual"},
    "scheduled": {"id": "Terjadwal", "en": "Scheduled"},
    "status_col": {"id": "Status", "en": "Status"},
    "level_col": {"id": "Level", "en": "Level"},
    "schedule_col": {"id": "Jadwal", "en": "Schedule"},
    "portions_col": {"id": "Porsi", "en": "Portions"},
    "no_history": {
        "id": "Belum ada riwayat pada periode ini.",
        "en": "No history for this period.",
    },

    # schedules page
    "active_schedules": {"id": "Jadwal aktif", "en": "Active schedules"},
    "next_feeding": {"id": "Pemberian berikutnya", "en": "Next feeding"},
    "device_sync": {"id": "Sinkronisasi perangkat", "en": "Device sync"},
    "synced": {"id": "Tersinkron", "en": "Synced"},
    "changes_pending": {"id": "Ada perubahan", "en": "Changes pending"},
    "waiting_device": {"id": "Menunggu perangkat", "en": "Waiting for device"},
    "send_to_device": {"id": "Kirim ke perangkat", "en": "Send to device"},
    "sending": {"id": "Mengirim...", "en": "Sending..."},
    "daily_schedules": {"id": "Jadwal harian", "en": "Daily schedules"},
    "daily_sub": {
        "id": "Jadwal berlaku setiap hari.",
        "en": "Schedules repeat every day.",
    },
    "add_schedule": {"id": "Tambah jadwal", "en": "Add schedule"},
    "every_day": {"id": "Setiap hari", "en": "Every day"},
    "active": {"id": "Aktif", "en": "Active"},
    "inactive": {"id": "Nonaktif", "en": "Inactive"},
    "edit_schedule": {"id": "Ubah jadwal", "en": "Edit schedule"},
    "schedule_name": {"id": "Nama jadwal", "en": "Schedule name"},
    "schedule_name_ph": {"id": "Contoh: Pakan pagi", "en": "Example: Morning feed"},
    "edit_short": {"id": "Ubah", "en": "Edit"},
    "schedule_form_sub": {
        "id": "Atur waktu dan porsi pakan harian.",
        "en": "Set the daily feeding time and portions.",
    },
    "time_label": {"id": "Waktu", "en": "Time"},
    "save_schedule": {"id": "Simpan jadwal", "en": "Save schedule"},
    "delete": {"id": "Hapus", "en": "Delete"},
    "delete_schedule_q": {"id": "Hapus jadwal?", "en": "Delete schedule?"},
    "delete_schedule_sub": {
        "id": "Tindakan ini menghapus jadwal dari database lokal.",
        "en": "This removes the schedule from the local database.",
    },
    "schedule_saved": {"id": "Jadwal disimpan secara lokal", "en": "Schedule saved locally"},
    "schedule_deleted": {"id": "Jadwal dihapus", "en": "Schedule deleted"},
    "no_schedules": {"id": "Belum ada jadwal.", "en": "No schedules yet."},
    "name_required": {"id": "Nama jadwal wajib diisi.", "en": "Schedule name is required."},
    "schedule_sent": {"id": "Jadwal terkirim · {id}", "en": "Schedules sent · {id}"},
    "send_failed": {"id": "Gagal mengirim perintah: {err}", "en": "Failed to send command: {err}"},

    # control page
    "security_title": {"id": "Hanya untuk jaringan lokal", "en": "Local network only"},
    "security_body": {
        "id": "Broker MQTT belum menggunakan autentikasi atau TLS. "
              "Jangan membuka akses ke internet publik.",
        "en": "The MQTT broker does not use authentication or TLS. "
              "Do not expose it to the public internet.",
    },
    "manual_feeding": {"id": "Pakan manual", "en": "Manual feeding"},
    "manual_feeding_sub": {
        "id": "Buka servo dan berikan pakan sekarang.",
        "en": "Open the servo and dispense feed now.",
    },
    "num_portions": {"id": "Jumlah porsi", "en": "Number of portions"},
    "device_state_sub": {
        "id": "Minta snapshot terbaru dari ESP32.",
        "en": "Request the latest snapshot from the ESP32.",
    },
    "request_fresh": {"id": "Minta status baru", "en": "Request fresh state"},
    "feed_threshold": {"id": "Ambang pakan", "en": "Feed threshold"},
    "feed_threshold_sub": {
        "id": "Kirim notifikasi saat level melewati batas.",
        "en": "Send an alert when the level passes this limit.",
    },
    "low_feed_alert": {"id": "Peringatan rendah", "en": "Low-feed alert"},
    "apply_threshold": {"id": "Terapkan ambang", "en": "Apply threshold"},
    "device_clock": {"id": "Jam perangkat", "en": "Device clock"},
    "device_clock_sub": {
        "id": "Sinkronkan RTC agar jadwal tetap akurat.",
        "en": "Sync the RTC so schedules remain accurate.",
    },
    "date": {"id": "Tanggal", "en": "Date"},
    "sync_rtc": {"id": "Sinkronkan RTC", "en": "Sync RTC"},
    "command_activity": {"id": "Aktivitas perintah", "en": "Command activity"},
    "command_activity_sub": {
        "id": "Perintah MQTT terbaru dan status ACK.",
        "en": "Recent MQTT commands and ACK status.",
    },
    "ack_timeout_badge": {"id": "Timeout 30 dtk", "en": "30s timeout"},
    "no_commands": {"id": "Belum ada perintah.", "en": "No commands yet."},
    "state_tile": {"id": "State", "en": "State"},
    "rssi_tile": {"id": "RSSI", "en": "RSSI"},
    "uptime_tile": {"id": "Uptime", "en": "Uptime"},

    # dialogs / feedback
    "confirm_feed_title": {
        "id": "Konfirmasi pemberian pakan",
        "en": "Confirm manual feeding",
    },
    "confirm_feed_sub": {
        "id": "Periksa kembali perintah sebelum dikirim ke perangkat.",
        "en": "Review the command before it is sent to the device.",
    },
    "amount": {"id": "Jumlah", "en": "Amount"},
    "action": {"id": "Aksi", "en": "Action"},
    "open_servo": {"id": "Buka servo sekarang", "en": "Open servo now"},
    "confirm_warning": {
        "id": "Pastikan area pemberian pakan aman dan hopper tidak kosong.",
        "en": "Make sure the feeding area is clear and the hopper is not empty.",
    },
    "yes_feed": {"id": "Ya, beri pakan", "en": "Yes, feed now"},
    "command_sent": {"id": "Perintah terkirim · {id}", "en": "Command sent · {id}"},
    "state_requested": {"id": "Permintaan status terkirim · {id}", "en": "State request sent · {id}"},
    "threshold_sent": {"id": "Ambang dikirim · {pct}%", "en": "Threshold sent · {pct}%"},
    "rtc_sent": {"id": "Perintah RTC terkirim · {id}", "en": "RTC command sent · {id}"},
    "all_marked_read": {"id": "Semua notifikasi ditandai dibaca", "en": "All alerts marked as read"},
}
