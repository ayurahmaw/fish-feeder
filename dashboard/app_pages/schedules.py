"""Schedules page: manage daily schedules and sync them to the device."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import data
import db
import ui
from actions import client_command, notify_command, notify_failure
from i18n import t

device = st.session_state["device"]


def _toggle_active(schedule_id: int) -> None:
    active = bool(st.session_state.get(f"active_{schedule_id}"))
    db.set_schedule_active(schedule_id, active)
    data.clear_reads()
    st.session_state["schedule_dirty"] = True


@st.dialog(t("add_schedule"))
def add_schedule() -> None:
    st.caption(t("schedule_form_sub"))
    name = st.text_input(t("schedule_name"), placeholder=t("schedule_name_ph"))
    left, right = st.columns(2)
    feed_time = left.time_input(
        t("time_label"), value=datetime.strptime("07:00", "%H:%M").time()
    )
    portions = right.number_input(t("num_portions"), 1, 50, value=1, step=1)
    if st.button(t("save_schedule"), type="primary", icon=":material/save:"):
        if not name.strip():
            st.error(t("name_required"))
            return
        db.insert_schedule(
            device_id=st.session_state["device"]["id"],
            name=name.strip(),
            feed_time=feed_time.strftime("%H:%M:%S"),
            portions=int(portions),
        )
        data.clear_reads()
        st.session_state["schedule_dirty"] = True
        ui.toast_after_rerun(t("schedule_saved"))
        st.rerun()


@st.dialog(t("edit_schedule"))
def edit_schedule(item: dict) -> None:
    st.caption(t("schedule_form_sub"))
    name = st.text_input(t("schedule_name"), value=item["name"])
    left, right = st.columns(2)
    feed_time = left.time_input(
        t("time_label"),
        value=datetime.strptime(item["feed_time"][:5], "%H:%M").time(),
    )
    portions = right.number_input(
        t("num_portions"), 1, 50, value=int(item["portions"]), step=1
    )
    if st.button(t("save_schedule"), type="primary", icon=":material/save:"):
        if not name.strip():
            st.error(t("name_required"))
            return
        db.update_schedule(
            item["id"],
            name=name.strip(),
            feed_time=feed_time.strftime("%H:%M:%S"),
            portions=int(portions),
        )
        data.clear_reads()
        st.session_state["schedule_dirty"] = True
        ui.toast_after_rerun(t("schedule_saved"))
        st.rerun()


@st.dialog(t("delete_schedule_q"))
def delete_schedule(item: dict) -> None:
    st.caption(t("delete_schedule_sub"))
    st.markdown(
        f"**{item['name']}** · {item['feed_time'][:5]} · "
        f"{item['portions']} {t('portions')}"
    )
    left, right = st.columns(2)
    if left.button(t("cancel")):
        st.rerun()
    if right.button(t("delete"), type="primary", icon=":material/delete:"):
        db.delete_schedule(item["id"])
        data.clear_reads()
        st.session_state["schedule_dirty"] = True
        ui.toast_after_rerun(t("schedule_deleted"))
        st.rerun()


@st.fragment(run_every="2s")
def render_overview() -> None:
    """Sync state follows the device: offline, pending changes, or synced."""
    status = data.status_of(device["id"]) or {}
    online = bool(status.get("is_online"))
    schedules = data.schedules(device["id"])
    active = [row for row in schedules if row["is_active"]]
    upcoming = ui.next_run(active)
    next_text = upcoming[0].strftime("%H:%M") if upcoming else "—"
    dirty = bool(st.session_state.get("schedule_dirty", False))

    with st.container(border=True):
        first, second, third, fourth = st.columns(
            [1, 1, 1.4, 1.6], vertical_alignment="center"
        )
        first.metric(t("active_schedules"), len(active))
        second.metric(t("next_feeding"), next_text)
        with third:
            st.caption(t("device_sync"))
            if not online:
                ui.badge(t("offline"), "critical")
                st.caption(t("waiting_device"))
            elif dirty:
                ui.badge(t("changes_pending"), "warning")
            else:
                ui.badge(t("synced"), "healthy")
        with fourth:
            with st.container(horizontal=True, horizontal_alignment="right"):
                if st.button(
                    t("send_to_device"),
                    type="primary",
                    icon=":material/send:",
                    disabled=not active or not online,
                    key="send_schedules",
                ):
                    try:
                        result = client_command(
                            device,
                            "set_schedule",
                            {"schedules": db.active_schedules(device["id"])},
                        )
                    except Exception as exc:
                        notify_failure(exc)
                    else:
                        st.session_state["schedule_dirty"] = False
                        notify_command(result, "schedule_sent")
                    st.rerun()


render_overview()

rows = data.schedules(device["id"])

with st.container(border=True):
    head_left, head_right = st.columns([3, 1], vertical_alignment="center")
    head_left.subheader(t("daily_schedules"))
    head_left.caption(t("daily_sub"))
    if head_right.button(
        t("add_schedule"), type="primary", icon=":material/add:", key="add_schedule"
    ):
        add_schedule()

    if not rows:
        ui.empty_state("event_repeat", t("no_schedules"), t("daily_sub"))
    else:
        for item in sorted(rows, key=lambda row: row["feed_time"]):
            with st.container(border=True):
                columns = st.columns(
                    [1.2, 4, 1.4, 1.1, 1.1], vertical_alignment="center"
                )
                columns[0].markdown(f"### {item['feed_time'][:5]}")
                with columns[1]:
                    st.markdown(f"**{item['name']}**")
                    st.caption(
                        f"{item['portions']} {t('portions')} · {t('every_day')}"
                    )
                columns[2].toggle(
                    t("active"),
                    value=bool(item["is_active"]),
                    key=f"active_{item['id']}",
                    on_change=_toggle_active,
                    args=(item["id"],),
                )
                if columns[3].button(
                    t("edit_short"),
                    icon=":material/edit:",
                    key=f"edit_{item['id']}",
                    type="tertiary",
                ):
                    edit_schedule(item)
                if columns[4].button(
                    t("delete"),
                    icon=":material/delete:",
                    key=f"delete_{item['id']}",
                    type="tertiary",
                ):
                    delete_schedule(item)
