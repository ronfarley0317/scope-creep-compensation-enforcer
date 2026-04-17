from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Any

from app.sources.base import RawMessage


def verify_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack HMAC-SHA256 request signature."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        return False
    try:
        # Reject requests older than 5 minutes to prevent replay attacks
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except (ValueError, TypeError):
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    computed = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def parse_event(payload: dict[str, Any]) -> RawMessage | None:
    """Extract a RawMessage from a Slack Events API payload, or None to ignore."""
    event_type = payload.get("type")

    # Slack URL verification handshake — caller must return the challenge directly
    if event_type == "url_verification":
        return None

    if event_type != "event_callback":
        return None

    event = payload.get("event", {})
    msg_type = event.get("type")
    if msg_type not in ("message", "app_mention"):
        return None
    if event.get("subtype"):  # skip edits, deletes, bot messages
        return None

    text = event.get("text", "").strip()
    if not text:
        return None

    channel_id = event.get("channel", "unknown")
    ts = event.get("ts", "")

    return RawMessage(
        id=f"{channel_id}:{ts}",
        text=text,
        channel=channel_id,
        source_type="slack",
        source_reference=f"slack:{channel_id}:{ts}",
        performed_on=_ts_to_date(ts),
        metadata={"ts": ts, "user": event.get("user", ""), "team": payload.get("team_id", "")},
    )


def _ts_to_date(ts: str) -> str | None:
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None
