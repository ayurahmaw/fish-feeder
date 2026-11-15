"""Mutating actions shared by the dashboard pages."""

from __future__ import annotations

import streamlit as st

import data
import ui
from commands import send_command
from config import TOPIC_PREFIX, COMMAND_TIMEOUT_SEC
from i18n import t
from runtime import get_runtime


def client_command(device: dict, type_: str, payload: dict | None = None):
    """Publish a command through the worker and return ``send_command``'s result."""
    runtime = get_runtime()
    return send_command(
        runtime.worker.client,
        TOPIC_PREFIX,
        device["device_code"],
        type_,
        payload or {},
    )


def notify_command(result: dict, message_key: str, **fmt) -> None:
    data.clear_reads()
    ui.toast_after_rerun(t(message_key, id=result["command_id"], **fmt))


def notify_failure(exc: Exception) -> None:
    ui.toast_after_rerun(
        t("send_failed", err=str(exc)), icon=":material/error:"
    )


@st.dialog(t("confirm_feed_title"))
def confirm_feed(portions: int) -> None:
    """Deliberate confirmation before a manual feed command leaves the app."""
    device = st.session_state["device"]
    st.caption(t("confirm_feed_sub"))
    st.markdown(f"**{t('device')}** · {device['name']} (`{device['device_code']}`)")
    st.markdown(f"**{t('amount')}** · {portions} {t('portions')}")
    st.markdown(f"**{t('action')}** · {t('open_servo')}")
    st.warning(t("confirm_warning"))
    st.caption(f"ACK timeout · {COMMAND_TIMEOUT_SEC}s")

    left, right = st.columns(2)
    if left.button(t("cancel")):
        st.rerun()
    if right.button(t("yes_feed"), type="primary", icon=":material/bolt:"):
        try:
            result = client_command(device, "manual_feed", {"portions": int(portions)})
        except Exception as exc:  # broker/publish failure
            st.error(t("send_failed", err=str(exc)))
            return
        notify_command(result, "command_sent")
        st.rerun()
