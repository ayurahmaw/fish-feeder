"""History page: audit feeding outcomes over time."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

import data
import ui
from i18n import status_label, t

device = st.session_state["device"]

with st.container(border=True):
    range_col, status_col = st.columns([3, 2], vertical_alignment="center")
    days = range_col.segmented_control(
        t("range"),
        options=[1, 7, 30],
        default=7,
        required=True,
        key="history_days",
        label_visibility="collapsed",
        format_func=lambda value: f"{value} " + (t("day") if value == 1 else t("days")),
    ) or 7
    selected = status_col.selectbox(
        t("status_col"),
        ["all", "success", "failed"],
        key="history_status",
        label_visibility="collapsed",
        format_func=lambda value: t("all_statuses") if value == "all" else status_label(value),
    )

now = data.sql_now()
rows = data.feeding_logs(
    device["id"],
    data.sql_stamp(now - timedelta(days=int(days))),
    data.sql_stamp(now),
)
visible = [
    row for row in rows if selected == "all" or row["status"] == selected
]

successful = sum(1 for row in visible if row["status"] == "success")
failed = len(visible) - successful
portions = sum(int(row["portions"] or 0) for row in visible)

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("total_events"), len(visible), border=True, icon=":material/history:")
c2.metric(t("successful"), successful, border=True, icon=":material/check_circle:")
c3.metric(t("failed_timeout"), failed, border=True, icon=":material/error:")
c4.metric(t("total_portions"), portions, border=True, icon=":material/bolt:")

with st.container(border=True):
    st.subheader(t("feeding_history"))
    st.caption(t("history_sub", days=int(days)))

    if not visible:
        ui.empty_state("history", t("no_history"), t("no_history"))
    else:
        table = pd.DataFrame(
            {
                t("time_col"): [ui.fmt_when(row["requested_at"]) for row in visible],
                t("trigger_col"): [
                    t("manual") if row["trigger_type"] == "manual" else t("scheduled")
                    for row in visible
                ],
                t("schedule_col"): [row["schedule_name"] or "—" for row in visible],
                t("portions_col"): [row["portions"] for row in visible],
                t("level_col"): [
                    f"{ui.level_text(row['feed_level_before_pct'])} → "
                    f"{ui.level_text(row['feed_level_after_pct'])}"
                    for row in visible
                ],
                t("status_col"): [[row["status"]] for row in visible],
            }
        )
        st.dataframe(
            table,
            hide_index=True,
            column_config={
                t("portions_col"): st.column_config.NumberColumn(
                    t("portions_col"), format="%d"
                ),
                t("status_col"): st.column_config.MultiselectColumn(
                    t("status_col"),
                    options=["success", "failed", "pending", "timeout"],
                    color=["green", "red", "blue", "orange"],
                    format_func=status_label,
                ),
            },
        )
