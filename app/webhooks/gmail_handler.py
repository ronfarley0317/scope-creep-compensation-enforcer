from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from app.sources.base import RawMessage

logger = logging.getLogger(__name__)


def verify_token(authorization_header: str | None) -> bool:
    """Validate the bearer token Google sends with Pub/Sub push notifications."""
    expected = os.environ.get("GMAIL_PUBSUB_TOKEN", "")
    if not expected or not authorization_header:
        return False
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return token.strip() == expected


def parse_event(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract (email_address, history_id) from a Pub/Sub push notification.

    The caller should use these to fetch new messages from the Gmail API
    and produce RawMessage objects from them.
    """
    try:
        message_data = payload.get("message", {}).get("data", "")
        decoded = base64.b64decode(message_data + "==").decode("utf-8")
        data = json.loads(decoded)
        return data.get("emailAddress"), str(data.get("historyId", ""))
    except Exception as exc:
        logger.warning("Failed to decode Gmail Pub/Sub payload: %s", exc)
        return None, None


def raw_message_from_gmail(
    message_id: str,
    snippet: str,
    thread_id: str,
    date_str: str | None,
    email_address: str,
) -> RawMessage:
    """Build a RawMessage from a Gmail message record."""
    return RawMessage(
        id=f"gmail:{message_id}",
        text=snippet,
        channel="gmail",
        source_type="gmail",
        source_reference=f"gmail:thread:{thread_id}",
        performed_on=date_str,
        metadata={"message_id": message_id, "email_address": email_address},
    )
