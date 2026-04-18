from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models.source_inputs import ScopeInput, WorkActivityInput
from app.services.retry import retry_with_backoff
from app.sources.base import SourceAdapter

_GRAPHQL_URL = "https://api.linear.app/graphql"

_ISSUES_QUERY = """
query Issues($filter: IssueFilter, $first: Int, $after: String) {
  issues(filter: $filter, first: $first, after: $after, orderBy: updatedAt) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      identifier
      title
      description
      estimate
      completedAt
      url
    }
  }
}
"""


class LinearWorkAdapter(SourceAdapter):
    """Fetch completed issues from a Linear team and normalize into WorkActivityInput."""

    def fetch_scope_inputs(self, client_config: dict[str, Any]) -> ScopeInput:
        raise NotImplementedError("LinearWorkAdapter does not implement scope ingestion.")

    def fetch_work_activity_inputs(self, client_config: dict[str, Any]) -> WorkActivityInput:
        settings = self._settings(client_config)
        issues = self._fetch_issues(settings)
        work_items = [self._normalize_issue(issue) for issue in issues]
        return WorkActivityInput(
            source_type="linear",
            source_reference=f"linear_team:{settings['team_id']}",
            payload={
                "source": {"provider": "linear", "team_id": settings["team_id"]},
                "period": self._derive_period(work_items),
                "work_items": work_items,
            },
        )

    def healthcheck(self, client_config: dict[str, Any]) -> dict[str, Any]:
        try:
            settings = self._settings(client_config)
        except ValueError as exc:
            return {"adapter": "linear_work", "healthy": False, "error": str(exc)}
        try:
            result = self._graphql(settings["token"], "{ viewer { id name email } }")
            viewer = result.get("data", {}).get("viewer", {})
            return {
                "adapter": "linear_work",
                "healthy": True,
                "team_id": settings["team_id"],
                "viewer_id": viewer.get("id"),
                "viewer_name": viewer.get("name"),
            }
        except Exception as exc:
            return {"adapter": "linear_work", "healthy": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def _fetch_issues(self, settings: dict[str, Any]) -> list[dict[str, Any]]:
        filter_obj: dict[str, Any] = {
            "team": {"id": {"eq": settings["team_id"]}},
            "completedAt": {"null": False},
        }
        if settings.get("project_id"):
            filter_obj["project"] = {"id": {"eq": settings["project_id"]}}
        if settings.get("completed_since"):
            filter_obj["completedAt"]["gte"] = settings["completed_since"]

        issues: list[dict[str, Any]] = []
        cursor = None
        while True:
            variables: dict[str, Any] = {"filter": filter_obj, "first": settings["page_size"]}
            if cursor:
                variables["after"] = cursor
            result = self._graphql(settings["token"], _ISSUES_QUERY, variables)
            page = result.get("data", {}).get("issues", {})
            issues.extend(page.get("nodes", []))
            page_info = page.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
        return issues

    def _normalize_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        completed_at = (issue.get("completedAt") or "")[:10] or None
        estimate = issue.get("estimate")
        return {
            "id": issue.get("id", ""),
            "description": issue.get("title") or issue.get("identifier") or "",
            "hours": float(estimate) if estimate is not None else None,
            "performed_on": completed_at,
            "source_type": "linear",
            "source_reference": f"linear:{issue.get('identifier', issue.get('id', ''))}",
            "source_excerpt": (issue.get("title") or "")[:160] or None,
        }

    def _derive_period(self, work_items: list[dict[str, Any]]) -> dict[str, Any]:
        dates = sorted(i["performed_on"] for i in work_items if i.get("performed_on"))
        return {"start_date": dates[0], "end_date": dates[-1]} if dates else {}

    def _settings(self, client_config: dict[str, Any]) -> dict[str, Any]:
        cfg = dict(client_config.get("linear", {}))
        if not cfg:
            raise ValueError("Missing 'linear' configuration block.")
        token = os.environ.get(cfg.get("api_key_env", "LINEAR_API_KEY"), "")
        if not token:
            raise ValueError("Missing LINEAR_API_KEY environment variable.")
        team_id = cfg.get("team_id", "")
        if not team_id:
            raise ValueError("Missing linear.team_id in client configuration.")
        return {
            "token": token,
            "team_id": team_id,
            "project_id": cfg.get("project_id", ""),
            "completed_since": cfg.get("completed_since", ""),
            "page_size": int(cfg.get("page_size", 50)),
        }

    @retry_with_backoff()
    def _graphql(
        self,
        token: str,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        request = Request(
            _GRAPHQL_URL,
            data=body,
            headers={
                "Authorization": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if result.get("errors"):
                raise RuntimeError(f"Linear GraphQL errors: {result['errors']}")
            return result
        except HTTPError as exc:
            raise RuntimeError(f"Linear API error {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
        except URLError as exc:
            raise RuntimeError(f"Linear API request failed: {exc.reason}") from exc
