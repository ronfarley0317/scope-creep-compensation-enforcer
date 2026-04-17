from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.retry import retry_with_backoff
from app.sources.base import ClassifiedMessage, MessageSourceAdapter, RawMessage

logger = logging.getLogger(__name__)

_BASE_URL = "https://slack.com/api"


class SlackMessageAdapter(MessageSourceAdapter):
    """Fetch messages from Slack channels and convert scope signals to work items."""

    def fetch_messages(
        self,
        client_config: dict[str, Any],
        since: str | None = None,
    ) -> list[RawMessage]:
        token = self._token()
        channel_ids: list[str] = client_config.get("slack_channel_ids", [])
        oldest = self._to_slack_ts(since) if since else None
        messages: list[RawMessage] = []
        for channel_id in channel_ids:
            try:
                raw = self._fetch_channel_messages(token, channel_id, oldest)
                messages.extend(raw)
            except Exception as exc:
                logger.warning("Slack channel %s fetch failed: %s", channel_id, exc)
        return messages

    def to_work_items(self, messages: list[ClassifiedMessage]) -> list[dict[str, Any]]:
        items = []
        for msg in messages:
            if not msg.is_scope_signal:
                continue
            raw = msg.raw
            items.append({
                "id": raw.id,
                "description": raw.text,
                "source_type": "slack",
                "source_reference": raw.source_reference,
                "source_excerpt": msg.excerpt,
                "performed_on": raw.performed_on,
                "hours": None,
                "quantity": None,
                "quantity_unit": None,
            })
        return items

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        try:
            token = self._token()
            result = self._api_call("auth.test", token, {})
            return {
                "adapter": "slack",
                "healthy": result.get("ok", False),
                "team": result.get("team"),
                "user": result.get("user"),
            }
        except Exception as exc:
            return {"adapter": "slack", "healthy": False, "error": str(exc)}

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _fetch_channel_messages(
        self,
        token: str,
        channel_id: str,
        oldest: str | None,
    ) -> list[RawMessage]:
        messages: list[RawMessage] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"channel": channel_id, "limit": 200}
            if oldest:
                params["oldest"] = oldest
            if cursor:
                params["cursor"] = cursor
            data = self._api_call("conversations.history", token, params)
            if not data.get("ok"):
                raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
            for msg in data.get("messages", []):
                if msg.get("type") != "message" or msg.get("subtype"):
                    continue
                ts = msg.get("ts", "")
                performed_on = self._ts_to_date(ts)
                messages.append(RawMessage(
                    id=f"{channel_id}:{ts}",
                    text=msg.get("text", ""),
                    channel=channel_id,
                    source_type="slack",
                    source_reference=f"slack:{channel_id}:{ts}",
                    performed_on=performed_on,
                    metadata={"ts": ts, "user": msg.get("user")},
                ))
            next_cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor
        return messages

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _api_call(self, method: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{_BASE_URL}/{method}?{urlencode(params)}"
        request = Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Slack HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc

    def _token(self) -> str:
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is not set")
        return token

    def _to_slack_ts(self, iso_ts: str) -> str:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return str(dt.timestamp())

    def _ts_to_date(self, ts: str) -> str | None:
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
