from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.retry import retry_with_backoff
from app.sources.base import SourceAdapter

_BASE = "https://{host}/rest/api/3"


class JiraWorkAdapter(SourceAdapter):
    """Fetch completed work from a Jira project and normalize it into WorkActivityInput."""

    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        raise NotImplementedError("JiraWorkAdapter does not implement scope ingestion.")

    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        settings = self._settings(client_config)
        issues = self._fetch_issues(settings)
        work_items = [self._normalize_issue(issue, settings) for issue in issues]
        return WorkActivityInput(
            source_type="jira",
            source_reference=f"jira_project:{settings['project_key']}",
            payload={
                "source": {"provider": "jira", "project_key": settings["project_key"]},
                "period": self._derive_period(work_items),
                "work_items": work_items,
            },
        )

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = self._settings(client_config)
        except ValueError as exc:
            return {"adapter": "jira_work", "healthy": False, "error": str(exc)}
        try:
            data = self._get(settings, "/myself")
            return {
                "adapter": "jira_work",
                "healthy": True,
                "project_key": settings["project_key"],
                "account_id": data.get("accountId"),
                "display_name": data.get("displayName"),
            }
        except Exception as exc:
            return {"adapter": "jira_work", "healthy": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def _fetch_issues(self, settings: dict[str, Any]) -> list[dict[str, Any]]:
        project_key = settings["project_key"]
        completed_since = settings.get("completed_since", "")
        jql = f'project = "{project_key}" AND statusCategory = Done'
        if completed_since:
            jql += f' AND resolutiondate >= "{completed_since}"'
        jql += " ORDER BY resolutiondate DESC"

        issues: list[dict[str, Any]] = []
        start_at = 0
        page_size = settings["page_size"]
        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": "summary,description,timespent,customfield_10016,resolutiondate,updated,status,issuetype",
            }
            data = self._get(settings, "/search", params)
            issues.extend(data.get("issues", []))
            total = data.get("total", 0)
            start_at += page_size
            if start_at >= total:
                break
        return issues

    def _normalize_issue(self, issue: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
        fields = issue.get("fields", {})
        host = settings["host"]
        issue_key = issue.get("key", issue.get("id", ""))
        timespent_sec = fields.get("timespent") or 0
        story_points = fields.get("customfield_10016")
        hours = (timespent_sec / 3600.0) if timespent_sec else (float(story_points) if story_points else None)
        performed_on = (
            (fields.get("resolutiondate") or fields.get("updated") or "")[:10] or None
        )
        return {
            "id": issue.get("id", issue_key),
            "description": fields.get("summary") or issue_key,
            "hours": hours,
            "performed_on": performed_on,
            "source_type": "jira",
            "source_reference": f"jira:{issue_key}",
            "source_excerpt": (fields.get("summary") or "")[:160] or None,
        }

    def _derive_period(self, work_items: list[dict[str, Any]]) -> dict[str, Any]:
        dates = sorted(i["performed_on"] for i in work_items if i.get("performed_on"))
        return {"start_date": dates[0], "end_date": dates[-1]} if dates else {}

    def _settings(self, client_config: dict[str, Any]) -> dict[str, Any]:
        cfg = dict(client_config.get("jira", {}))
        if not cfg:
            raise ValueError("Missing 'jira' configuration block.")
        host = os.environ.get(cfg.get("host_env", "JIRA_HOST"), cfg.get("host", ""))
        if not host:
            raise ValueError("Missing Jira host (set JIRA_HOST or jira.host).")
        email = os.environ.get(cfg.get("email_env", "JIRA_EMAIL"), "")
        token = os.environ.get(cfg.get("api_token_env", "JIRA_API_TOKEN"), "")
        if not email or not token:
            raise ValueError("Missing JIRA_EMAIL or JIRA_API_TOKEN environment variables.")
        project_key = cfg.get("project_key", "")
        if not project_key:
            raise ValueError("Missing jira.project_key in client configuration.")
        return {
            "host": host,
            "auth": base64.b64encode(f"{email}:{token}".encode()).decode(),
            "project_key": project_key,
            "completed_since": cfg.get("completed_since", ""),
            "page_size": int(cfg.get("page_size", 100)),
        }

    @retry_with_backoff()
    def _get(
        self, settings: dict[str, Any], path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        host = settings["host"]
        qs = f"?{urlencode(params)}" if params else ""
        url = f"https://{host}/rest/api/3{path}{qs}"
        request = Request(url, headers={
            "Authorization": f"Basic {settings['auth']}",
            "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Jira API error {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except URLError as exc:
            raise RuntimeError(f"Jira API request failed: {exc.reason}") from exc
