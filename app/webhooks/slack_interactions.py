from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import BackgroundTasks

from app.services.alert_service import AlertService
from app.services.approval_store import ApprovalStore
from app.services.client_env import client_env_context
from app.services.config_loader import load_client_bundle
from app.services.invoice_delivery import InvoiceDelivery
from app.webhooks.slack_handler import verify_signature
from app.workflows.run_single_client import _resolve_client_layout

logger = logging.getLogger(__name__)

_APPROVE_ACTION = "approve_invoice"
_REJECT_ACTION = "reject_invoice"


def parse_payload(raw_body: bytes) -> dict[str, Any] | None:
    """Slack sends interactions as application/x-www-form-urlencoded with a 'payload' field."""
    try:
        parsed = parse_qs(raw_body.decode("utf-8"))
        payload_str = parsed.get("payload", [None])[0]
        if not payload_str:
            return None
        return json.loads(payload_str)
    except Exception as exc:
        logger.warning("Failed to parse Slack interaction payload: %s", exc)
        return None


def handle_interaction(
    payload: dict[str, Any],
    configs_root: Path,
    background_tasks: BackgroundTasks | None = None,
) -> dict[str, Any]:
    """Dispatch an incoming Slack interaction to the correct handler.

    Returns a Slack response dict (can be sent back as the HTTP response body).
    """
    interaction_type = payload.get("type")
    if interaction_type != "block_actions":
        return {}

    actions = payload.get("actions", [])
    if not actions:
        return {}

    action = actions[0]
    action_id = action.get("action_id", "")
    value = action.get("value", "")
    user_id = payload.get("user", {}).get("id", "unknown")
    message_ts = payload.get("message", {}).get("ts", "")
    channel_id = payload.get("channel", {}).get("id", "")

    if action_id not in (_APPROVE_ACTION, _REJECT_ACTION):
        return {}

    # Button value format: "client_id:run_id"
    parts = value.split(":", 1)
    if len(parts) != 2:
        logger.warning("Unexpected interaction button value: %r", value)
        return {}
    client_id, run_id = parts

    if action_id == _APPROVE_ACTION:
        return _handle_approve(client_id, run_id, user_id, message_ts, channel_id, configs_root, background_tasks)
    return _handle_reject(client_id, run_id, user_id, message_ts, channel_id, configs_root)


def _handle_approve(
    client_id: str,
    run_id: str,
    user_id: str,
    message_ts: str,
    channel_id: str,
    configs_root: Path,
    background_tasks: BackgroundTasks | None = None,
) -> dict[str, Any]:
    client_dir = configs_root / client_id
    if not client_dir.exists():
        logger.error("Approval for unknown client: %s", client_id)
        return {}

    client_root, config_dir = _resolve_client_layout(client_dir)
    with client_env_context(client_root):
        bundle = load_client_bundle(config_dir)
        client_config = {**bundle.client, "_client_dir": str(config_dir), "_client_root": str(client_root)}
        store = ApprovalStore(client_root)
        entry = store.approve(run_id, user_id)

        if entry:
            logger.info("Invoice approved: client=%s run=%s by=%s", client_id, run_id, user_id)
            _update_alert_message(client_config, channel_id, message_ts, "approved", user_id, entry)
            if background_tasks is not None:
                background_tasks.add_task(InvoiceDelivery().send, client_config, entry, store)
            else:
                InvoiceDelivery().send(client_config, entry, store)

    return {}


def _handle_reject(
    client_id: str,
    run_id: str,
    user_id: str,
    message_ts: str,
    channel_id: str,
    configs_root: Path,
) -> dict[str, Any]:
    client_dir = configs_root / client_id
    if not client_dir.exists():
        logger.error("Rejection for unknown client: %s", client_id)
        return {}

    client_root, config_dir = _resolve_client_layout(client_dir)
    with client_env_context(client_root):
        bundle = load_client_bundle(config_dir)
        client_config = {**bundle.client, "_client_dir": str(config_dir), "_client_root": str(client_root)}
        store = ApprovalStore(client_root)
        entry = store.reject(run_id, user_id)

        if entry:
            logger.info("Invoice rejected: client=%s run=%s by=%s", client_id, run_id, user_id)
            _update_alert_message(client_config, channel_id, message_ts, "rejected", user_id, entry)

    return {}


def _update_alert_message(
    client_config: dict[str, Any],
    channel_id: str,
    message_ts: str,
    action: str,
    decided_by: str,
    entry: dict[str, Any],
) -> None:
    from app.services.alert_service import _get_token
    alert_cfg = client_config.get("internal_alert", {})
    token = _get_token(alert_cfg)
    if not token or not channel_id or not message_ts:
        return
    client_name = client_config.get("client_name", client_config.get("client_id", "unknown"))
    excerpt = entry.get("excerpt", "")
    AlertService().send_approval_decision(token, channel_id, message_ts, action, decided_by, client_name, excerpt)
