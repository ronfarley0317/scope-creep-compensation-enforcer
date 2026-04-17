from __future__ import annotations

import logging
import os
from typing import Any

from app.sources.base import RawMessage

logger = logging.getLogger(__name__)


def verify_client_state(notifications: list[dict[str, Any]]) -> bool:
    """Verify the clientState on all incoming Graph notifications."""
    expected = os.environ.get("OUTLOOK_CLIENT_STATE", "")
    if not expected:
        return False
    return all(n.get("clientState") == expected for n in notifications)


def parse_events(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract (subscription_id, resource) pairs from a Graph change notification.

    The caller uses the resource path to fetch the full message from Graph API.
    Returns an empty list if the payload is not a valid notification.
    """
    notifications = payload.get("value", [])
    if not isinstance(notifications, list):
        return []
    if not verify_client_state(notifications):
        logger.warning("Outlook webhook: clientState mismatch — ignoring")
        return []

    results = []
    for n in notifications:
        change_type = n.get("changeType", "")
        resource = n.get("resource", "")
        subscription_id = n.get("subscriptionId", "")
        if change_type == "created" and resource and subscription_id:
            results.append((subscription_id, resource))
    return results


def raw_message_from_outlook(
    message_id: str,
    subject: str,
    body_preview: str,
    received_date: str | None,
    sender: str,
) -> RawMessage:
    """Build a RawMessage from an Outlook message record."""
    text = f"{subject}: {body_preview}".strip(": ") if subject else body_preview
    return RawMessage(
        id=f"outlook:{message_id}",
        text=text,
        channel="outlook",
        source_type="outlook",
        source_reference=f"outlook:{message_id}",
        performed_on=received_date,
        metadata={"message_id": message_id, "sender": sender},
    )
