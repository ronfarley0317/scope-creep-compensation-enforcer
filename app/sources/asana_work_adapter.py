from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.retry import retry_with_backoff
from app.sources.base import SourceAdapter


class AsanaWorkAdapter(SourceAdapter):
    """Fetch work activity from an Asana project and normalize it into WorkActivityInput."""

    base_url = "https://app.asana.com/api/1.0"

    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        raise NotImplementedError("AsanaWorkAdapter does not implement scope ingestion.")

    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        settings = self._settings(client_config)
        task_records = self._fetch_tasks(settings)
        work_items = [self._normalize_task(task) for task in task_records]
        period = self._derive_period(work_items)
        return WorkActivityInput(
            source_type="asana",
            source_reference=f"asana_project:{settings['project_gid']}",
            payload={
                "source": {
                    "provider": "asana",
                    "project_gid": settings["project_gid"],
                },
                "period": period,
                "work_items": work_items,
            },
        )

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = self._settings(client_config)
        except ValueError as exc:
            return {
                "adapter": "asana_work",
                "healthy": False,
                "error": str(exc),
            }

        try:
            user_payload = self._request_json(
                "/users/me",
                settings,
                query={"opt_fields": "gid,name"},
            )
            return {
                "adapter": "asana_work",
                "healthy": True,
                "project_gid": settings["project_gid"],
                "workspace_gid": settings.get("workspace_gid"),
                "actor_gid": user_payload["data"].get("gid"),
                "actor_name": user_payload["data"].get("name"),
            }
        except Exception as exc:  # pragma: no cover - exercised through mocked tests
            return {
                "adapter": "asana_work",
                "healthy": False,
                "project_gid": settings["project_gid"],
                "workspace_gid": settings.get("workspace_gid"),
                "error": str(exc),
            }

    def _fetch_tasks(self, settings: dict[str, Any]) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            query = {
                "limit": settings["page_size"],
                "completed_since": settings["completed_since"],
                "opt_fields": (
                    "gid,name,notes,completed,completed_at,created_at,modified_at,permalink_url,"
                    "custom_fields.gid,custom_fields.name,custom_fields.resource_subtype,"
                    "custom_fields.display_value,custom_fields.number_value,custom_fields.text_value,"
                    "custom_fields.enum_value.name,custom_fields.multi_enum_values.name"
                ),
            }
            if offset:
                query["offset"] = offset
            payload = self._request_json(
                f"/projects/{settings['project_gid']}/tasks",
                settings,
                query=query,
            )
            tasks.extend(payload.get("data", []))
            next_page = payload.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
        return tasks

    def _normalize_task(self, task: dict[str, Any]) -> dict[str, Any]:
        performed_on = self._performed_on(task)
        source_excerpt = (task.get("notes") or task.get("name") or "").strip()[:160] or None
        normalized = {
            "id": task["gid"],
            "name": task.get("name"),
            "description": task.get("notes") or task.get("name") or "",
            "completed": bool(task.get("completed")),
            "completed_at": task.get("completed_at"),
            "created_at": task.get("created_at"),
            "modified_at": task.get("modified_at"),
            "performed_on": performed_on,
            "source_type": "task",
            "source_reference": task.get("permalink_url") or task["gid"],
            "source_excerpt": source_excerpt,
        }
        for field in task.get("custom_fields", []):
            value = self._custom_field_value(field)
            if value in (None, "", []):
                continue
            safe_name = self._safe_key(field.get("name", "custom_field"))
            normalized[safe_name] = value
            normalized[f"custom_field_{field.get('gid')}"] = value
        return normalized

    def _custom_field_value(self, field: dict[str, Any]) -> Any:
        subtype = field.get("resource_subtype")
        if subtype == "number":
            return field.get("number_value")
        if subtype == "text":
            return field.get("text_value")
        if subtype == "enum":
            enum_value = field.get("enum_value") or {}
            return enum_value.get("name")
        if subtype == "multi_enum":
            return ", ".join(
                value.get("name", "")
                for value in field.get("multi_enum_values", [])
                if value.get("name")
            )
        return field.get("display_value")

    def _performed_on(self, task: dict[str, Any]) -> str | None:
        for key in ("completed_at", "modified_at", "created_at"):
            value = task.get(key)
            if value:
                return str(value)[:10]
        return None

    def _derive_period(self, work_items: list[dict[str, Any]]) -> dict[str, str] | dict[str, Any]:
        dates = sorted(item["performed_on"] for item in work_items if item.get("performed_on"))
        if not dates:
            return {}
        return {"start_date": dates[0], "end_date": dates[-1]}

    def _settings(self, client_config: dict[str, Any]) -> dict[str, Any]:
        settings = dict(client_config.get("asana", {}))
        if not settings:
            raise ValueError("Missing 'asana' configuration for Asana work source.")
        token_env = settings.get("access_token_env", "ASANA_ACCESS_TOKEN")
        token = os.environ.get(token_env)
        if not token:
            raise ValueError(f"Missing Asana access token in environment variable {token_env}.")
        project_gid = settings.get("project_gid")
        if not project_gid:
            raise ValueError("Missing Asana project_gid in client configuration.")
        settings["access_token"] = token
        settings["page_size"] = int(settings.get("page_size", 100))
        settings["completed_since"] = settings.get("completed_since", "now")
        return settings

    @retry_with_backoff()
    def _request_json(
        self,
        path: str,
        settings: dict[str, Any],
        *,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_string = f"?{urlencode(query)}" if query else ""
        request = Request(
            f"{self.base_url}{path}{query_string}",
            headers={
                "Authorization": f"Bearer {settings['access_token']}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Asana API request failed with HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise RuntimeError(f"Asana API request failed: {exc.reason}") from exc

    def _safe_key(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
        while "__" in cleaned:
            cleaned = cleaned.replace("__", "_")
        return cleaned.strip("_") or "custom_field"
