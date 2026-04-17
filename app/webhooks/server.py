from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response

from app.webhooks import gmail_handler, outlook_handler, slack_handler, slack_interactions
from app.workflows.process_webhook_event import process_webhook_event
from app.workflows.run_webhook_pipeline import run_full_pipeline_and_alert

logger = logging.getLogger(__name__)


def create_app(configs_root: Path) -> FastAPI:
    app = FastAPI(title="Scope Creep Enforcer — Webhook Server")
    app.state.configs_root = configs_root

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------- Slack interactions
    @app.post("/slack/interactions")
    async def slack_interactions_handler(
        request: Request,
        background_tasks: BackgroundTasks,
        x_slack_request_timestamp: Optional[str] = Header(default=None),
        x_slack_signature: Optional[str] = Header(default=None),
    ) -> Any:
        body = await request.body()

        if not x_slack_request_timestamp or not x_slack_signature:
            raise HTTPException(status_code=400, detail="Missing Slack signature headers")
        if not slack_handler.verify_signature(body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

        payload = slack_interactions.parse_payload(body)
        if not payload:
            raise HTTPException(status_code=400, detail="Could not parse interaction payload")

        slack_interactions.handle_interaction(payload, app.state.configs_root, background_tasks)
        # Slack expects a 200 with empty body to acknowledge the interaction
        return {}

    # ------------------------------------------------------------------ Slack
    @app.post("/webhook/{client_id}/slack")
    async def slack_webhook(
        client_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        x_slack_request_timestamp: Optional[str] = Header(default=None),
        x_slack_signature: Optional[str] = Header(default=None),
    ) -> Any:
        body = await request.body()
        payload = await request.json()

        # URL verification challenge — respond before signature check
        if payload.get("type") == "url_verification":
            return {"challenge": payload.get("challenge")}

        if not x_slack_request_timestamp or not x_slack_signature:
            raise HTTPException(status_code=400, detail="Missing Slack signature headers")

        if not slack_handler.verify_signature(body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

        raw_message = slack_handler.parse_event(payload)
        if raw_message is None:
            return {"status": "ignored"}

        result = _process_and_schedule(client_id, raw_message, background_tasks, app.state.configs_root)
        return _public_result(result)

    # ------------------------------------------------------------------ Gmail
    @app.post("/webhook/{client_id}/gmail")
    async def gmail_webhook(
        client_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        authorization: Optional[str] = Header(default=None),
    ) -> Any:
        if not gmail_handler.verify_token(authorization):
            raise HTTPException(status_code=401, detail="Invalid Pub/Sub token")

        payload = await request.json()
        email_address, history_id = gmail_handler.parse_event(payload)

        if not email_address or not history_id:
            return {"status": "ignored"}

        from app.sources.base import RawMessage
        raw_message = RawMessage(
            id=f"gmail:history:{history_id}",
            text=f"New email activity for {email_address} (history {history_id})",
            channel="gmail",
            source_type="gmail",
            source_reference=f"gmail:history:{history_id}",
            performed_on=None,
            metadata={"email_address": email_address, "history_id": history_id},
        )

        result = _process_and_schedule(client_id, raw_message, background_tasks, app.state.configs_root)
        return _public_result(result)

    # --------------------------------------------------------------- Outlook
    @app.post("/webhook/{client_id}/outlook")
    async def outlook_webhook(
        client_id: str,
        request: Request,
        background_tasks: BackgroundTasks,
        validation_token: Optional[str] = None,
    ) -> Any:
        # Microsoft Graph subscription validation handshake
        if validation_token:
            return Response(content=validation_token, media_type="text/plain")

        payload = await request.json()
        event_pairs = outlook_handler.parse_events(payload)

        if not event_pairs:
            return {"status": "ignored"}

        results = []
        for subscription_id, resource in event_pairs:
            raw_message = outlook_handler.raw_message_from_outlook(
                message_id=resource,
                subject="",
                body_preview=f"New message notification from subscription {subscription_id}",
                received_date=None,
                sender="",
            )
            result = _process_and_schedule(client_id, raw_message, background_tasks, app.state.configs_root)
            results.append(_public_result(result))

        return {"status": "processed", "results": results}

    return app


def _process_and_schedule(
    client_id: str,
    raw_message: Any,
    background_tasks: BackgroundTasks,
    configs_root: Path,
) -> dict[str, Any]:
    """Run fast webhook classification and schedule the full pipeline if creep is found."""
    try:
        result = process_webhook_event(client_id, raw_message, configs_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Webhook classification error for client %s: %s", client_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")

    if result.get("is_scope_signal") and result.get("creep_events"):
        work_item_dicts = result.get("_work_item_dicts", [])
        excerpt = result.get("excerpt", raw_message.text[:120])
        background_tasks.add_task(
            run_full_pipeline_and_alert,
            client_id,
            work_item_dicts,
            excerpt,
            configs_root,
        )
        logger.info(
            "Scope signal from %s — full pipeline queued for client %s",
            raw_message.source_type,
            client_id,
        )

    return result


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    """Strip internal keys before returning to the webhook caller."""
    return {k: v for k, v in result.items() if not k.startswith("_")}
