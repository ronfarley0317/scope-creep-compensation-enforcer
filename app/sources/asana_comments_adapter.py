from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.retry import retry_with_backoff
from app.sources.base import ClassifiedMessage, MessageSourceAdapter, RawMessage

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.asana.com/api/1.0"


class AsanaCommentsAdapter(MessageSourceAdapter):
    """Fetch task comments (stories) from Asana and convert scope signals to work items.

    Uses the same ASANA_ACCESS_TOKEN as AsanaWorkAdapter.
    Requires 'asana.project_gid' in client config.
    """

    def fetch_messages(
        self,
        client_config: dict[str, Any],
        since: str | None = None,
    ) -> list[RawMessage]:
        settings = self._settings(client_config)
        try:
            task_gids = self._fetch_task_gids(settings)
            messages: list[RawMessage] = []
            for task_gid in task_gids:
                try:
                    stories = self._fetch_stories(task_gid, settings, since)
                    messages.extend(stories)
                except Exception as exc:
                    logger.warning("Asana stories fetch for task %s failed: %s", task_gid, exc)
            return messages
        except Exception as exc:
            logger.warning("Asana comments fetch failed: %s", exc)
            return []

    def to_work_items(self, messages: list[ClassifiedMessage]) -> list[dict[str, Any]]:
        items = []
        for msg in messages:
            if not msg.is_scope_signal:
                continue
            raw = msg.raw
            items.append({
                "id": raw.id,
                "description": raw.text,
                "source_type": "asana_comment",
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
            settings = self._settings(client_config)
            data = self._request_json("/users/me", settings, query={"opt_fields": "gid,name"})
            return {
                "adapter": "asana_comment",
                "healthy": True,
                "actor_gid": data["data"].get("gid"),
                "actor_name": data["data"].get("name"),
            }
        except Exception as exc:
            return {"adapter": "asana_comment", "healthy": False, "error": str(exc)}

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _fetch_task_gids(self, settings: dict[str, Any]) -> list[str]:
        query = {
            "limit": 100,
            "opt_fields": "gid",
        }
        data = self._request_json(f"/projects/{settings['project_gid']}/tasks", settings, query=query)
        return [task["gid"] for task in data.get("data", [])]

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _fetch_stories(
        self,
        task_gid: str,
        settings: dict[str, Any],
        since: str | None,
    ) -> list[RawMessage]:
        query = {"opt_fields": "gid,type,resource_subtype,text,created_at,created_by.name"}
        data = self._request_json(f"/tasks/{task_gid}/stories", settings, query=query)
        messages = []
        for story in data.get("data", []):
            if story.get("type") != "comment":
                continue
            created_at = story.get("created_at", "")
            if since and created_at and created_at < since:
                continue
            text = (story.get("text") or "").strip()
            if not text:
                continue
            performed_on = created_at[:10] if created_at else None
            story_gid = story.get("gid", "")
            messages.append(RawMessage(
                id=story_gid,
                text=text,
                channel="asana_comment",
                source_type="asana_comment",
                source_reference=f"asana:task:{task_gid}:story:{story_gid}",
                performed_on=performed_on,
                metadata={"task_gid": task_gid, "author": (story.get("created_by") or {}).get("name")},
            ))
        return messages

    @retry_with_backoff()
    def _request_json(
        self,
        path: str,
        settings: dict[str, Any],
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_string = f"?{urlencode(query)}" if query else ""
        request = Request(
            f"{_BASE_URL}{path}{query_string}",
            headers={
                "Authorization": f"Bearer {settings['access_token']}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Asana API HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except URLError as exc:
            raise RuntimeError(f"Asana API network error: {exc.reason}") from exc

    def _settings(self, client_config: dict[str, Any]) -> dict[str, Any]:
        settings = dict(client_config.get("asana", {}))
        if not settings:
            raise ValueError("Missing 'asana' configuration block in client config.")
        token_env = settings.get("access_token_env", "ASANA_ACCESS_TOKEN")
        token = os.environ.get(token_env)
        if not token:
            raise ValueError(f"Missing Asana access token in {token_env}")
        project_gid = settings.get("project_gid")
        if not project_gid:
            raise ValueError("Missing asana.project_gid in client config.")
        settings["access_token"] = token
        return settings
