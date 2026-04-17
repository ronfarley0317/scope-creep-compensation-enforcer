from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.alert_service import AlertService
from app.services.approval_store import ApprovalStore
from app.services.client_env import client_env_context
from app.services.config_loader import load_client_bundle
from app.workflows.run_single_client import _resolve_client_layout, run_single_client

logger = logging.getLogger(__name__)


def run_full_pipeline_and_alert(
    client_id: str,
    work_item_dicts: list[dict[str, Any]],
    excerpt: str,
    configs_root: Path,
) -> None:
    """Run the full pipeline for a client (injecting webhook-sourced work items) then alert.

    Designed to be called as a background task after a webhook event fires.
    The webhook has already responded to the caller — this runs without a deadline.
    """
    client_dir = configs_root / client_id
    client_root, config_dir = _resolve_client_layout(client_dir)
    alert = AlertService()

    with client_env_context(client_root):
        bundle = load_client_bundle(config_dir)
        client_config = {
            **bundle.client,
            "_client_dir": str(config_dir),
            "_client_root": str(client_root),
        }

        try:
            result = run_single_client(client_dir, extra_work_items=work_item_dicts)
            run_id = result.get("run_id", "unknown")
            creep_events = result.get("comparison", {}).get("creep_events", [])
            artifact_paths = result.get("output_paths", {})

            logger.info(
                "Webhook pipeline complete for %s — run=%s, %d creep events",
                client_id, run_id, len(creep_events),
            )

            message_ts = alert.send_creep_detected(
                client_config,
                run_id=run_id,
                excerpt=excerpt,
                creep_events=creep_events,
                artifact_paths=artifact_paths,
            )

            # Store pending approval so the interactions endpoint can resolve it
            alert_cfg = client_config.get("internal_alert", {})
            channel_id = alert_cfg.get("slack_channel_id", "")
            if message_ts and channel_id and creep_events:
                store = ApprovalStore(client_root)
                store.create(
                    run_id=run_id,
                    client_id=client_id,
                    excerpt=excerpt,
                    creep_events=creep_events,
                    artifact_paths=artifact_paths,
                    currency=client_config.get("currency", "USD"),
                    slack_channel_id=channel_id,
                    slack_message_ts=message_ts,
                )
                logger.info("Approval pending for run %s", run_id)

        except Exception as exc:
            logger.error(
                "Full pipeline failed for client %s after webhook: %s",
                client_id, exc, exc_info=True,
            )
            alert.send_error(client_config, excerpt, str(exc))
