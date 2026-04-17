from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MessageDeduplicator:
    """Tracks processed message IDs per channel to prevent double-processing.

    State is persisted as JSON in client/<id>/state/seen_messages.json.
    """

    def __init__(self, client_root: Path) -> None:
        self._state_path = client_root / "state" / "seen_messages.json"
        self._seen: dict[str, set[str]] = self._load()

    def filter_new(self, channel: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return only messages whose 'id' field has not been seen for this channel."""
        seen = self._seen.get(channel, set())
        return [m for m in messages if m.get("id") not in seen]

    def mark_seen(self, channel: str, message_ids: list[str]) -> None:
        """Persist message IDs as processed for this channel."""
        if channel not in self._seen:
            self._seen[channel] = set()
        self._seen[channel].update(message_ids)
        self._save()

    def _load(self) -> dict[str, set[str]]:
        if not self._state_path.exists():
            return {}
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            return {k: set(v) for k, v in raw.items()}
        except Exception:
            return {}

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: sorted(v) for k, v in self._seen.items()}
        self._state_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
