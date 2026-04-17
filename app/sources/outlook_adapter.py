from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.retry import retry_with_backoff
from app.sources.base import ClassifiedMessage, MessageSourceAdapter, RawMessage

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
_SCOPE = "https://graph.microsoft.com/.default"


class OutlookMessageAdapter(MessageSourceAdapter):
    """Fetch client emails from Outlook/Microsoft 365 via Microsoft Graph API.

    Requires OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, OUTLOOK_TENANT_ID env vars.
    """

    def fetch_messages(
        self,
        client_config: dict[str, Any],
        since: str | None = None,
    ) -> list[RawMessage]:
        try:
            token = self._get_access_token()
            mailbox = client_config.get("outlook_mailbox", "me")
            folder = client_config.get("outlook_folder", "inbox")
            messages = self._fetch_mail(token, mailbox, folder, since)
            return messages
        except Exception as exc:
            logger.warning("Outlook fetch failed: %s", exc)
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
                "source_type": "outlook",
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
            token = self._get_access_token()
            data = self._request_json(f"{_GRAPH_BASE}/me", token)
            return {
                "adapter": "outlook",
                "healthy": True,
                "display_name": data.get("displayName"),
                "mail": data.get("mail"),
            }
        except Exception as exc:
            return {"adapter": "outlook", "healthy": False, "error": str(exc)}

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _fetch_mail(
        self,
        token: str,
        mailbox: str,
        folder: str,
        since: str | None,
    ) -> list[RawMessage]:
        select = "id,subject,receivedDateTime,bodyPreview,from,body"
        params: dict[str, Any] = {
            "$top": 100,
            "$select": select,
            "$orderby": "receivedDateTime desc",
        }
        if since:
            params["$filter"] = f"receivedDateTime ge {since[:19]}Z"

        if mailbox == "me":
            url = f"{_GRAPH_BASE}/me/mailFolders/{folder}/messages?{urlencode(params)}"
        else:
            url = f"{_GRAPH_BASE}/users/{mailbox}/mailFolders/{folder}/messages?{urlencode(params)}"

        data = self._request_json(url, token)
        messages = []
        for item in data.get("value", []):
            raw = self._parse_item(item)
            if raw:
                messages.append(raw)
        return messages

    def _parse_item(self, item: dict[str, Any]) -> RawMessage | None:
        msg_id = item.get("id", "")
        subject = item.get("subject", "")
        received = item.get("receivedDateTime", "")
        performed_on = received[:10] if received else None
        body_content = (item.get("body") or {}).get("content", "")
        preview = item.get("bodyPreview", "")
        text = f"{subject}\n{preview or body_content}".strip()
        if not text:
            return None
        sender = ((item.get("from") or {}).get("emailAddress") or {}).get("address", "")
        return RawMessage(
            id=msg_id,
            text=text,
            channel="outlook",
            source_type="outlook",
            source_reference=f"outlook:message:{msg_id}",
            performed_on=performed_on,
            metadata={"subject": subject, "from": sender},
        )

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _request_json(self, url: str, token: str) -> dict[str, Any]:
        request = Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        try:
            with urlopen(request, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"Graph HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc

    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def _get_access_token(self) -> str:
        client_id = os.environ.get("OUTLOOK_CLIENT_ID", "")
        client_secret = os.environ.get("OUTLOOK_CLIENT_SECRET", "")
        tenant_id = os.environ.get("OUTLOOK_TENANT_ID", "")
        for name, val in [("OUTLOOK_CLIENT_ID", client_id), ("OUTLOOK_CLIENT_SECRET", client_secret), ("OUTLOOK_TENANT_ID", tenant_id)]:
            if not val:
                raise ValueError(f"{name} environment variable is not set")

        url = _TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)
        body = urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": _SCOPE,
            "grant_type": "client_credentials",
        }).encode()
        request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urlopen(request, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["access_token"]
        except HTTPError as exc:
            raise RuntimeError(f"MSAL token error HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc
