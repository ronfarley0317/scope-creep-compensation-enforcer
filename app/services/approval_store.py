from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_REJECTED = "rejected"


class ApprovalStore:
    """Persists invoice approval state per client in state/pending_approvals.json.

    Each entry is keyed by run_id and tracks status, artifact paths, and
    who approved/rejected it (Slack user ID + timestamp).
    """

    def __init__(self, client_root: Path) -> None:
        self._path = client_root / "state" / "pending_approvals.json"
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Write

    def create(
        self,
        run_id: str,
        client_id: str,
        excerpt: str,
        creep_events: list[dict[str, Any]],
        artifact_paths: dict[str, str],
        currency: str,
        slack_channel_id: str,
        slack_message_ts: str,
    ) -> None:
        total = sum(e.get("estimated_amount") or 0.0 for e in creep_events)
        self._data[run_id] = {
            "run_id": run_id,
            "client_id": client_id,
            "status": _STATUS_PENDING,
            "excerpt": excerpt,
            "creep_event_count": len(creep_events),
            "estimated_amount": total,
            "currency": currency,
            "artifact_paths": artifact_paths,
            "created_at": _now(),
            "decided_at": None,
            "decided_by": None,
            "slack_channel_id": slack_channel_id,
            "slack_message_ts": slack_message_ts,
        }
        self._save()

    def approve(self, run_id: str, decided_by: str) -> dict[str, Any] | None:
        return self._decide(run_id, _STATUS_APPROVED, decided_by)

    def reject(self, run_id: str, decided_by: str) -> dict[str, Any] | None:
        return self._decide(run_id, _STATUS_REJECTED, decided_by)

    def record_delivery(self, run_id: str, delivery: dict[str, Any]) -> None:
        entry = self._data.get(run_id)
        if entry:
            entry["delivery"] = delivery
            self._save()

    def _decide(self, run_id: str, status: str, decided_by: str) -> dict[str, Any] | None:
        entry = self._data.get(run_id)
        if not entry:
            logger.warning("Approval entry not found for run_id %s", run_id)
            return None
        if entry["status"] != _STATUS_PENDING:
            logger.info("Approval already decided for run_id %s: %s", run_id, entry["status"])
            return entry
        entry["status"] = status
        entry["decided_at"] = _now()
        entry["decided_by"] = decided_by
        self._save()
        return entry

    # ------------------------------------------------------------------
    # Read

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self._data.get(run_id)

    def list_pending(self) -> list[dict[str, Any]]:
        return [e for e in self._data.values() if e["status"] == _STATUS_PENDING]

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    # ------------------------------------------------------------------
    # Persistence

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
