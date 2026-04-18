from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.retry import retry_with_backoff
from app.sources.base import SourceAdapter

_BASE = "https://api.clickup.com/api/v2"


class ClickUpWorkAdapter(SourceAdapter):
    """Fetch closed tasks from a ClickUp list and normalize into WorkActivityInput."""

    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        raise NotImplementedError("ClickUpWorkAdapter does not implement scope ingestion.")

    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        settings = self._settings(client_config)
        tasks = self._fetch_tasks(settings)
        work_items = [self._normalize_task(task) for task in tasks]
        return WorkActivityInput(
            source_type="clickup",
            source_reference=f"clickup_list:{settings['list_id']}",
            payload={
                "source": {"provider": "clickup", "list_id": settings["list_id"]},
                "period": self._derive_period(work_items),
                "work_items": work_items,
            },
        )

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = self._settings(client_config)
        except ValueError as exc:
            return {"adapter": "clickup_work", "healthy": False, "error": str(exc)}
        try:
            data = self._get(settings, "/user")
            user = data.get("user", {})
            return {
                "adapter": "clickup_work",
                "healthy": True,
                "list_id": settings["list_id"],
                "user_id": user.get("id"),
                "username": user.get("username"),
            }
        except Exception as exc:
            return {"adapter": "clickup_work", "healthy": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def _fetch_tasks(self, settings: dict[str, Any]) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        page = 0
        completed_since_ms = self._to_epoch_ms(settings.get("completed_since", ""))

        while True:
            params: dict[str, Any] = {
                "statuses[]": "complete",
                "page": page,
                "limit": settings["page_size"],
                "include_closed": "true",
            }
            if completed_since_ms:
                params["date_done_gt"] = completed_since_ms

            data = self._get(settings, f"/list/{settings['list_id']}/task", params)
            batch = data.get("tasks", [])
            tasks.extend(batch)
            if len(batch) < settings["page_size"]:
                break
            page += 1
        return tasks

    def _normalize_task(self, task: dict[str, Any]) -> dict[str, Any]:
        time_spent_ms = task.get("time_spent") or 0
        hours = (int(time_spent_ms) / 3_600_000.0) if time_spent_ms else None
        date_closed_ms = task.get("date_closed")
        performed_on = self._epoch_ms_to_date(date_closed_ms) if date_closed_ms else None
        task_id = task.get("id", "")
        return {
            "id": task_id,
            "description": task.get("name") or task_id,
            "hours": hours,
            "performed_on": performed_on,
            "source_type": "clickup",
            "source_reference": f"clickup:{task_id}",
            "source_excerpt": (task.get("name") or "")[:160] or None,
        }

    def _derive_period(self, work_items: list[dict[str, Any]]) -> dict[str, Any]:
        dates = sorted(i["performed_on"] for i in work_items if i.get("performed_on"))
        return {"start_date": dates[0], "end_date": dates[-1]} if dates else {}

    def _settings(self, client_config: dict[str, Any]) -> dict[str, Any]:
        cfg = dict(client_config.get("clickup", {}))
        if not cfg:
            raise ValueError("Missing 'clickup' configuration block.")
        token = os.environ.get(cfg.get("api_token_env", "CLICKUP_API_TOKEN"), "")
        if not token:
            raise ValueError("Missing CLICKUP_API_TOKEN environment variable.")
        list_id = str(cfg.get("list_id", ""))
        if not list_id:
            raise ValueError("Missing clickup.list_id in client configuration.")
        return {
            "token": token,
            "list_id": list_id,
            "completed_since": cfg.get("completed_since", ""),
            "page_size": int(cfg.get("page_size", 100)),
        }

    @retry_with_backoff()
    def _get(
        self, settings: dict[str, Any], path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        qs = f"?{urlencode(params, doseq=True)}" if params else ""
        request = Request(
            f"{_BASE}{path}{qs}",
            headers={"Authorization": settings["token"], "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"ClickUp API error {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except URLError as exc:
            raise RuntimeError(f"ClickUp API request failed: {exc.reason}") from exc

    @staticmethod
    def _to_epoch_ms(date_str: str) -> int | None:
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            return None

    @staticmethod
    def _epoch_ms_to_date(epoch_ms: Any) -> str | None:
        try:
            dt = datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            return None
