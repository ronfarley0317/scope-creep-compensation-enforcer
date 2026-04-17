from __future__ import annotations

import base64
import json
import logging
import os
from email import message_from_bytes
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.retry import retry_with_backoff
from app.sources.base import ClassifiedMessage, MessageSourceAdapter, RawMessage

logger = logging.getLogger(__name__)

_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailMessageAdapter(MessageSourceAdapter):
    """Fetch client emails from Gmail and convert scope signals to work items.

    Uses a service account JSON for auth. Set GMAIL_SERVICE_ACCOUNT_PATH env var.
    """

    def fetch_messages(
        self,
        client_config: dict[str, Any],
        since: str | None = None,
    ) -> list[RawMessage]:
        token = self._get_access_token()
        query = client_config.get("gmail_query", "")
        if since:
            date_part = since[:10].replace("-", "/")
            query = f"{query} after:{date_part}".strip()
        try:
            thread_ids = self._list_threads(token, query)
            messages: list[RawMessage] = []
            for thread_id in thread_ids:
                msgs = self._fetch_thread_messages(token, thread_id)
                messages.extend(msgs)
            return messages
        except Exception as exc:
            logger.warning("Gmail fetch failed: %s", exc)
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
                "source_type": "gmail",
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
            profile = self._request_json(f"{_GMAIL_BASE}/users/me/profile", token)
            return {
                "adapter": "gmail",
                "healthy": True,
                "email": profile.get("emailAddress"),
                "total_messages": profile.get("messagesTotal"),
            }
        except Exception as exc:
            return {"adapter": "gmail", "healthy": False, "error": str(exc)}

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _list_threads(self, token: str, query: str) -> list[str]:
        params: dict[str, Any] = {"maxResults": 100}
        if query:
            params["q"] = query
        url = f"{_GMAIL_BASE}/users/me/threads?{urlencode(params)}"
        data = self._request_json(url, token)
        return [t["id"] for t in data.get("threads", [])]

    @retry_with_backoff(max_attempts=5, base_delay=1.0)
    def _fetch_thread_messages(self, token: str, thread_id: str) -> list[RawMessage]:
        url = f"{_GMAIL_BASE}/users/me/threads/{thread_id}?format=full"
        data = self._request_json(url, token)
        messages = []
        for msg in data.get("messages", []):
            raw = self._parse_message(msg)
            if raw:
                messages.append(raw)
        return messages

    def _parse_message(self, msg: dict[str, Any]) -> RawMessage | None:
        msg_id = msg.get("id", "")
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("subject", "")
        date_str = headers.get("date", "")
        performed_on = self._parse_date(date_str)
        body = self._extract_body(msg.get("payload", {}))
        text = f"{subject}\n{body}".strip()
        if not text:
            return None
        return RawMessage(
            id=msg_id,
            text=text,
            channel="gmail",
            source_type="gmail",
            source_reference=f"gmail:message:{msg_id}",
            performed_on=performed_on,
            metadata={"subject": subject, "from": headers.get("from", "")},
        )

    def _extract_body(self, payload: dict[str, Any]) -> str:
        mime_type = payload.get("mimeType", "")
        if mime_type == "text/plain":
            data = (payload.get("body") or {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
        for part in payload.get("parts", []):
            text = self._extract_body(part)
            if text:
                return text
        return ""

    def _parse_date(self, date_str: str) -> str | None:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

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
            raise RuntimeError(f"Gmail HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}") from exc

    def _get_access_token(self) -> str:
        creds_path = os.environ.get("GMAIL_SERVICE_ACCOUNT_PATH", "")
        if not creds_path:
            raise ValueError("GMAIL_SERVICE_ACCOUNT_PATH environment variable is not set")
        creds = json.loads(open(creds_path).read())
        return self._jwt_bearer_token(creds)

    def _jwt_bearer_token(self, creds: dict[str, Any]) -> str:
        """Obtain an access token via JWT assertion (service account flow)."""
        import time
        import hmac
        import hashlib

        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT"}
        claim = {
            "iss": creds["client_email"],
            "scope": _SCOPE,
            "aud": _TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }

        def b64(data: Any) -> str:
            return base64.urlsafe_b64encode(
                json.dumps(data).encode()
            ).rstrip(b"=").decode()

        unsigned = f"{b64(header)}.{b64(claim)}"

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            private_key = serialization.load_pem_private_key(
                creds["private_key"].encode(), password=None
            )
            signature = private_key.sign(unsigned.encode(), padding.PKCS1v15(), hashes.SHA256())
        except ImportError:
            raise RuntimeError(
                "Install 'cryptography' to use Gmail service account auth: pip install cryptography"
            )

        jwt = f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

        body = urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        }).encode()
        request = Request(_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["access_token"]
