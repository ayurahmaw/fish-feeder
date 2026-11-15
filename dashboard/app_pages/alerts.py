"""Alerts page: review and resolve feed/device notifications."""

from __future__ import annotations

import streamlit as st

import data
import db
import ui
from i18n import t

device = st.session_state["device"]

notes = data.notifications(device["id"], False)
unread = sum(1 for note in notes if not note["is_read"])
warnings = sum(1 for note in notes if note["severity"] == "warning")
critical = sum(1 for note in notes if note["severity"] == "critical")

first, second, third = st.columns(3)
first.metric(t("unread"), unread, border=True, icon=":material/notifications:")
second.metric(t("warnings"), warnings, border=True, icon=":material/warning:")
third.metric(t("critical"), critical, border=True, icon=":material/error:")

with st.container(border=True):
    filter_col, action_col = st.columns([3, 2], vertical_alignment="center")
    with filter_col:
        selected = st.segmented_control(
            t("status_col"),
            options=["all", "unread", "critical"],
            default="all",
            required=True,
            key="alert_filter",
            label_visibility="collapsed",
            format_func=lambda value: t(value),
        ) or "all"
    with action_col:
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                t("mark_all_read"),
                icon=":material/done_all:",
                disabled=unread == 0,
                key="alert_mark_all",
            ):
                db.mark_all_notifications_read(device["id"])
                data.clear_reads()
                ui.toast_after_rerun(t("all_marked_read"))
                st.rerun()

    if selected == "unread":
        visible = [note for note in notes if not note["is_read"]]
    elif selected == "critical":
        visible = [note for note in notes if note["severity"] == "critical"]
    else:
        visible = notes

    if not visible:
        ui.empty_state("task_alt", t("all_clear"), t("no_alerts_filter"))
    else:
        for note in visible[:50]:
            with st.container(border=True):
                icon_col, body_col, action_col = st.columns(
                    [1, 8, 2], vertical_alignment="center"
                )
                icon_col.markdown(
                    f"## :material/{ui.SEVERITY_ICON.get(note['severity'], 'info')}:"
                )
                with body_col:
                    with st.container(horizontal=True):
                        ui.badge(
                            note["type"].replace("_", " "),
                            ui.SEVERITY_TONE.get(note["severity"], "info"),
                        )
                        if not note["is_read"]:
                            ui.badge(t("unread"), "info")
                    st.markdown(f"**{note['title'] or note['type']}**")
                    st.caption(note["message"])
                    level = (
                        f" · {ui.level_text(note['feed_level_pct'])}"
                        if note["feed_level_pct"] is not None
                        else ""
                    )
                    st.caption(f"{ui.fmt_when(note['created_at'])}{level}")
                if note["is_read"]:
                    action_col.caption(t("read"))
                elif action_col.button(
                    t("mark_read"),
                    icon=":material/check:",
                    key=f"read_{note['id']}",
                ):
                    db.mark_notification_read(note["id"])
                    data.clear_reads()
                    ui.toast_after_rerun(t("mark_read"))
                    st.rerun()

        if len(visible) > 50:
            st.caption(t("showing_n", n=50, total=len(visible)))
