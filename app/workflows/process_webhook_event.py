from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.client_env import client_env_context
from app.services.comparison_engine import ComparisonEngine
from app.services.config_loader import load_client_bundle
from app.services.message_classifier import MessageClassifier
from app.services.message_deduplicator import MessageDeduplicator
from app.services.scope_normalizer import ScopeNormalizer
from app.sources.base import RawMessage
from app.sources.resolver import SourceResolver
from app.workflows.run_single_client import _resolve_client_layout

logger = logging.getLogger(__name__)


def process_webhook_event(
    client_id: str,
    raw_message: RawMessage,
    configs_root: Path,
) -> dict[str, Any]:
    """Classify and compare a single inbound message against the client's contract.

    Returns immediately — does not run the full invoice/artifact pipeline.
    The caller decides whether to trigger a full run based on the result.
    """
    client_dir = configs_root / client_id
    if not client_dir.exists():
        raise ValueError(f"Unknown client: {client_id!r}")

    client_root, config_dir = _resolve_client_layout(client_dir)
    with client_env_context(client_root):
        return _process_inner(raw_message, client_root, config_dir)


def _process_inner(
    raw_message: RawMessage,
    client_root: Path,
    config_dir: Path,
) -> dict[str, Any]:
    deduplicator = MessageDeduplicator(client_root)
    seen = deduplicator._seen.get(raw_message.channel, set())
    if raw_message.id in seen:
        return {
            "status": "duplicate",
            "message_id": raw_message.id,
            "is_scope_signal": False,
            "creep_events": [],
        }

    classifier = MessageClassifier()
    classified_msgs = classifier.classify([raw_message])
    classified = classified_msgs[0]

    deduplicator.mark_seen(raw_message.channel, [raw_message.id])

    if not classified.is_scope_signal:
        return {
            "status": "processed",
            "message_id": raw_message.id,
            "is_scope_signal": False,
            "confidence": classified.confidence,
            "classification_method": classified.classification_method,
            "creep_events": [],
        }

    bundle = load_client_bundle(config_dir)
    client_config = {
        **bundle.client,
        "_client_dir": str(config_dir),
        "_client_root": str(client_root),
        "message_source_types": [raw_message.source_type],
    }

    resolver = SourceResolver()
    try:
        adapter = resolver.resolve_message_adapters(client_config)[0]
        work_item_dicts = adapter.to_work_items([classified])
    except ValueError:
        # Unknown source_type — build a generic work item dict
        work_item_dicts = [_generic_work_item(classified)]

    if not work_item_dicts:
        return {
            "status": "processed",
            "message_id": raw_message.id,
            "is_scope_signal": True,
            "confidence": classified.confidence,
            "excerpt": classified.excerpt,
            "classification_method": classified.classification_method,
            "creep_events": [],
        }

    normalizer = ScopeNormalizer(client_config, bundle.contract_rules, bundle.field_mapping)
    scope_adapter = SourceResolver().resolve_scope_adapter(client_config)
    scope_input = scope_adapter.fetch_scope_inputs(client_config)
    contract = normalizer.normalize_contract(scope_input)
    work_items = normalizer.normalize_work_log_from_dicts(work_item_dicts)

    comparison_result = ComparisonEngine().compare(contract, work_items)

    logger.info(
        "Webhook event %s: is_scope_signal=True, creep_events=%d",
        raw_message.id,
        len(comparison_result.creep_events),
    )

    return {
        "status": "processed",
        "message_id": raw_message.id,
        "is_scope_signal": True,
        "confidence": classified.confidence,
        "excerpt": classified.excerpt,
        "classification_method": classified.classification_method,
        "creep_events": [e.to_dict() for e in comparison_result.creep_events],
        # Passed to the background full-pipeline run so it can inject this item
        "_work_item_dicts": work_item_dicts,
    }


def _generic_work_item(classified: Any) -> dict[str, Any]:
    raw = classified.raw
    return {
        "id": raw.id,
        "description": raw.text,
        "source_type": raw.source_type,
        "source_reference": raw.source_reference,
        "source_excerpt": classified.excerpt,
        "performed_on": raw.performed_on,
        "hours": None,
        "quantity": None,
        "quantity_unit": None,
    }
