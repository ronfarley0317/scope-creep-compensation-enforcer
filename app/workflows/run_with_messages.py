from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Any

from app.services.client_env import client_env_context
from app.services.config_loader import load_client_bundle
from app.workflows.poll_messages import poll_all_channels
from app.workflows.run_single_client import run_single_client, _resolve_client_layout, _run_single_client_inner

logger = logging.getLogger(__name__)


def run_client_with_messages(client_dir: str | Path) -> dict[str, Any]:
    """Run the full scope creep pipeline augmented with live message channel inputs.

    1. Poll all configured message channels → scope-signal WorkItems
    2. Inject those items into the comparison engine alongside the file-based work log
    3. Run the standard pipeline (comparison → compensation → artifacts)

    Falls back gracefully to file-only mode if all channels fail.
    """
    base_path = Path(client_dir)
    client_root, config_dir = _resolve_client_layout(base_path)

    with client_env_context(client_root):
        return _run_with_messages_inner(base_path, client_root, config_dir)


def _run_with_messages_inner(
    base_path: Path,
    client_root: Path,
    config_dir: Path,
) -> dict[str, Any]:
    bundle = load_client_bundle(config_dir)
    client_config = {
        **bundle.client,
        "_client_dir": str(config_dir),
        "_client_root": str(client_root),
    }

    message_work_items = poll_all_channels(client_root, client_config)
    if message_work_items:
        logger.info(
            "Injecting %d message-sourced work items into pipeline",
            len(message_work_items),
        )

    return _run_single_client_inner(base_path, client_root, config_dir, message_work_items)


def run_client_with_messages_loop(
    client_dir: str | Path,
    poll_interval_minutes: int = 60,
) -> None:
    """Run continuously, polling channels every poll_interval_minutes minutes."""
    logger.info(
        "Starting polling loop — interval: %d minutes",
        poll_interval_minutes,
    )
    while True:
        try:
            result = run_client_with_messages(client_dir)
            logger.info("Run complete: %s", result.get("terminal_summary", "").splitlines()[0])
        except Exception as exc:
            logger.error("Run failed: %s", exc, exc_info=True)

        logger.info("Next poll in %d minutes", poll_interval_minutes)
        time.sleep(poll_interval_minutes * 60)
