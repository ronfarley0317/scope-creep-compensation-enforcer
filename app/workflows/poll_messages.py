from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.channel_logger import get_channel_logger
from app.services.credential_validator import CredentialValidator
from app.services.message_classifier import MessageClassifier
from app.services.message_deduplicator import MessageDeduplicator
from app.sources.resolver import SourceResolver

logger = logging.getLogger(__name__)


def poll_all_channels(
    client_root: Path,
    client_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Poll all configured message channels and return scope-signal work items.

    - Validates credentials first; invalid channels are skipped, never fatal.
    - Deduplicates messages across runs.
    - Classifies with keyword scan → Claude for borderline cases.
    - Returns a list of work item dicts ready for the comparison engine.
    """
    log = get_channel_logger(client_root)
    message_source_types: list[str] = client_config.get("message_source_types", [])

    if not message_source_types:
        log.info("No message_source_types configured — skipping channel poll")
        return []

    validation = CredentialValidator().validate(message_source_types)
    log.info(
        "Credential validation: valid=%s failed=%s",
        validation.valid_channels,
        validation.failed_channels,
    )
    for warning in validation.warnings:
        log.warning(warning)

    if not validation.has_any_valid:
        log.warning("All message channels failed credential validation — skipping poll")
        return []

    deduplicator = MessageDeduplicator(client_root)
    classifier = MessageClassifier()
    resolver = SourceResolver()
    last_checked = _load_last_checked(client_root)
    all_work_items: list[dict[str, Any]] = []

    for channel in validation.valid_channels:
        log.info("Polling channel: %s", channel)
        try:
            adapter = resolver.resolve_message_adapters({**client_config, "message_source_types": [channel]})[0]
            since = last_checked.get(channel)
            raw_messages = adapter.fetch_messages(client_config, since=since)
            log.info("Channel %s: fetched %d messages", channel, len(raw_messages))

            new_messages = deduplicator.filter_new(channel, raw_messages)
            log.info("Channel %s: %d new (unseen) messages", channel, len(new_messages))

            if not new_messages:
                continue

            classified = classifier.classify(new_messages)
            signals = [m for m in classified if m.is_scope_signal]
            log.info("Channel %s: %d scope signals detected", channel, len(signals))

            work_items = adapter.to_work_items(signals)
            all_work_items.extend(work_items)

            deduplicator.mark_seen(channel, [m.id for m in new_messages])

        except Exception as exc:
            log.error("Channel %s poll failed (skipping): %s", channel, exc, exc_info=True)

    _save_last_checked(client_root, last_checked, validation.valid_channels)
    log.info("Poll complete — %d scope-signal work items collected", len(all_work_items))
    return all_work_items


def _load_last_checked(client_root: Path) -> dict[str, str]:
    path = client_root / "state" / "last_checked.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_last_checked(
    client_root: Path,
    existing: dict[str, str],
    channels: list[str],
) -> None:
    now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    updated = {**existing, **{ch: now for ch in channels}}
    path = client_root / "state" / "last_checked.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
