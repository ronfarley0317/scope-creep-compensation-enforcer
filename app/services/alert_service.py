from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
_SLACK_UPDATE_URL = "https://slack.com/api/chat.update"


class AlertService:
    """Send internal team alerts when scope creep is detected.

    Reads alert config from client_config under the 'internal_alert' key:
        internal_alert:
          slack_bot_token_env: ALERT_SLACK_BOT_TOKEN
          slack_channel_id: C0YOURTEAM
    """

    def send_creep_detected(
        self,
        client_config: dict[str, Any],
        run_id: str,
        excerpt: str,
        creep_events: list[dict[str, Any]],
        artifact_paths: dict[str, str] | None = None,
    ) -> str | None:
        """Post a Block Kit alert with Approve/Reject buttons.

        Returns the Slack message timestamp (ts) if sent, None otherwise.
        """
        alert_cfg = client_config.get("internal_alert", {})
        channel_id = alert_cfg.get("slack_channel_id", "")
        token = _get_token(alert_cfg)

        if not channel_id or not token:
            logger.info(
                "Alert skipped — internal_alert not configured "
                "(set internal_alert.slack_channel_id and slack_bot_token_env)"
            )
            return None

        client_id = client_config.get("client_id", "unknown")
        blocks = _build_alert_blocks(client_config, run_id, client_id, excerpt, creep_events, artifact_paths)
        fallback_text = _build_fallback_text(client_config, excerpt, creep_events)
        return self._post_blocks(token, channel_id, fallback_text, blocks)

    def send_approval_decision(
        self,
        token: str,
        channel_id: str,
        message_ts: str,
        action: str,
        decided_by: str,
        client_name: str,
        excerpt: str,
    ) -> None:
        """Update the alert message in-place to reflect the approval decision."""
        icon = ":white_check_mark:" if action == "approved" else ":x:"
        label = "Approved" if action == "approved" else "Rejected"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":rotating_light: *Scope creep — {client_name}*\n"
                        f'> "{excerpt[:160]}"\n\n'
                        f"{icon} *{label}* by <@{decided_by}>"
                    ),
                },
            }
        ]
        body = json.dumps(
            {"channel": channel_id, "ts": message_ts, "blocks": blocks, "text": f"{label} by {decided_by}"}
        ).encode()
        self._call(token, _SLACK_UPDATE_URL, body)

    def send_error(
        self,
        client_config: dict[str, Any],
        excerpt: str,
        error: str,
    ) -> None:
        alert_cfg = client_config.get("internal_alert", {})
        channel_id = alert_cfg.get("slack_channel_id", "")
        token = _get_token(alert_cfg)
        if not channel_id or not token:
            return
        client_name = client_config.get("client_name", client_config.get("client_id", "unknown"))
        text = (
            f":warning: *Scope creep pipeline error — {client_name}*\n"
            f'Trigger: "{excerpt[:120]}"\n'
            f"Error: {error}"
        )
        body = json.dumps({"channel": channel_id, "text": text}).encode()
        self._call(token, _SLACK_POST_URL, body)

    def _post_blocks(
        self, token: str, channel_id: str, fallback_text: str, blocks: list[dict[str, Any]]
    ) -> str | None:
        body = json.dumps({"channel": channel_id, "text": fallback_text, "blocks": blocks}).encode()
        result = self._call(token, _SLACK_POST_URL, body)
        return result.get("ts") if result else None

    def _call(self, token: str, url: str, body: bytes) -> dict[str, Any]:
        request = Request(
            url,
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            if not result.get("ok"):
                logger.warning("Slack API error (%s): %s", url, result.get("error"))
            return result
        except HTTPError as exc:
            logger.warning("Slack HTTP %s: %s", exc.code, exc.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            logger.warning("Slack call failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Block Kit builders

def _build_alert_blocks(
    client_config: dict[str, Any],
    run_id: str,
    client_id: str,
    excerpt: str,
    creep_events: list[dict[str, Any]],
    artifact_paths: dict[str, str] | None,
) -> list[dict[str, Any]]:
    client_name = client_config.get("client_name", client_id)
    currency = client_config.get("currency", "USD")
    total = sum(e.get("estimated_amount") or 0.0 for e in creep_events)
    event_count = len(creep_events)

    header_text = (
        f":rotating_light: *Scope creep detected — {client_name}*\n"
        f'> "{excerpt[:160]}"\n\n'
        f"*Events:* {event_count}  |  *Estimated:* {currency} {total:.2f}"
    )
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header_text}}
    ]

    if creep_events:
        bullet_lines = []
        for event in creep_events:
            calc = event.get("revenue_impact_calculation", "")
            explanation = event.get("client_explanation", "")
            bullet_lines.append(f"• {explanation}  (`{calc}`)")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(bullet_lines)},
        })

    if artifact_paths:
        invoice_md = artifact_paths.get("run_invoice_markdown") or artifact_paths.get("invoice_markdown", "")
        report = artifact_paths.get("run_client_report") or artifact_paths.get("client_report", "")
        path_lines = []
        if invoice_md:
            path_lines.append(f"Invoice draft: `{invoice_md}`")
        if report:
            path_lines.append(f"Full report: `{report}`")
        if path_lines:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(path_lines)},
            })

    button_value = f"{client_id}:{run_id}"
    blocks.append({
        "type": "actions",
        "block_id": "invoice_approval",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve Invoice"},
                "style": "primary",
                "action_id": "approve_invoice",
                "value": button_value,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Reject"},
                "style": "danger",
                "action_id": "reject_invoice",
                "value": button_value,
                "confirm": {
                    "title": {"type": "plain_text", "text": "Reject this invoice?"},
                    "text": {
                        "type": "mrkdwn",
                        "text": "This dismisses the scope creep alert without billing the client.",
                    },
                    "confirm": {"type": "plain_text", "text": "Yes, reject"},
                    "deny": {"type": "plain_text", "text": "Cancel"},
                },
            },
        ],
    })

    return blocks


def _build_fallback_text(
    client_config: dict[str, Any],
    excerpt: str,
    creep_events: list[dict[str, Any]],
) -> str:
    client_name = client_config.get("client_name", client_config.get("client_id", "unknown"))
    currency = client_config.get("currency", "USD")
    total = sum(e.get("estimated_amount") or 0.0 for e in creep_events)
    return f"Scope creep detected — {client_name}: \"{excerpt[:80]}\" | {currency} {total:.2f}"


def _get_token(alert_cfg: dict[str, Any]) -> str:
    token_env = alert_cfg.get("slack_bot_token_env", "ALERT_SLACK_BOT_TOKEN")
    return os.environ.get(token_env, "")
