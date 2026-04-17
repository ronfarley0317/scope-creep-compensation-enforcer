from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.sources.base import ClassifiedMessage, RawMessage

logger = logging.getLogger(__name__)

_SCOPE_CREEP_KEYWORDS = [
    "can you also",
    "one more thing",
    "in addition to",
    "while you're at it",
    "while you are at it",
    "quick extra",
    "add this",
    "add a",
    "outside the scope",
    "not in the original",
    "not part of the original",
    "beyond what we agreed",
    "on top of that",
    "also need",
    "also want",
    "another thing",
    "new request",
    "additional",
    "extra page",
    "extra revision",
    "one more revision",
    "change order",
    "can we add",
    "could you add",
    "can we also",
    "could you also",
    "small addition",
    "minor addition",
    "just one more",
    "forgot to mention",
    "actually, can you",
    "actually can you",
]

_BORDERLINE_KEYWORDS = [
    "update",
    "change",
    "modify",
    "adjust",
    "revise",
    "tweak",
    "different",
    "instead",
    "replace",
    "switch",
]

_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
_CLAUDE_TIMEOUT = 10


class MessageClassifier:
    """Hybrid classifier: keyword scan first, Claude for borderline messages.

    Phase 1 — keyword scan: definite signals → classified immediately.
    Phase 2 — borderline only → Claude API call.
    Phase 3 — Claude failure → falls back to keyword-only result.
    """

    def classify(self, messages: list[RawMessage]) -> list[ClassifiedMessage]:
        results = []
        for msg in messages:
            classified = self._classify_one(msg)
            results.append(classified)
        return results

    def _classify_one(self, msg: RawMessage) -> ClassifiedMessage:
        text_lower = msg.text.lower()

        if self._has_keyword(text_lower, _SCOPE_CREEP_KEYWORDS):
            excerpt = self._extract_excerpt(msg.text, _SCOPE_CREEP_KEYWORDS)
            return ClassifiedMessage(
                raw=msg,
                is_scope_signal=True,
                confidence="high",
                excerpt=excerpt,
                classification_method="keyword",
            )

        if self._has_keyword(text_lower, _BORDERLINE_KEYWORDS):
            try:
                return self._classify_with_claude(msg)
            except Exception as exc:
                logger.warning("Claude classifier failed for msg %s, using keyword fallback: %s", msg.id, exc)
                excerpt = self._extract_excerpt(msg.text, _BORDERLINE_KEYWORDS)
                return ClassifiedMessage(
                    raw=msg,
                    is_scope_signal=False,
                    confidence="low",
                    excerpt=excerpt,
                    classification_method="keyword_fallback",
                )

        return ClassifiedMessage(
            raw=msg,
            is_scope_signal=False,
            confidence="high",
            excerpt=msg.text[:120],
            classification_method="keyword",
        )

    def _classify_with_claude(self, msg: RawMessage) -> ClassifiedMessage:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set — cannot use Claude classifier")

        import urllib.request
        import urllib.error

        prompt = (
            "You are a scope creep detector for a client services team. "
            "Classify the following message as one of: scope_change, in_scope, or unclear.\n\n"
            "A 'scope_change' is any request for work that was NOT in the original contract "
            "(new deliverables, extra revisions, additional pages, work beyond agreed limits).\n"
            "'in_scope' means the message is about work clearly covered by the original agreement.\n"
            "'unclear' means you cannot determine from the message alone.\n\n"
            f"Message:\n{msg.text[:800]}\n\n"
            "Respond with valid JSON only:\n"
            '{"classification": "scope_change"|"in_scope"|"unclear", "confidence": "high"|"medium"|"low", '
            '"excerpt": "<brief quote from message that justifies your decision>"}'
        )

        body = json.dumps({
            "model": _CLAUDE_MODEL,
            "max_tokens": 256,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        request = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=_CLAUDE_TIMEOUT) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))

        raw_text = response_data["content"][0]["text"].strip()
        parsed = json.loads(raw_text)
        classification = parsed.get("classification", "unclear")
        confidence = parsed.get("confidence", "medium")
        excerpt = parsed.get("excerpt", msg.text[:120])

        return ClassifiedMessage(
            raw=msg,
            is_scope_signal=(classification == "scope_change"),
            confidence=confidence,
            excerpt=excerpt,
            classification_method="claude",
        )

    def _has_keyword(self, text_lower: str, keywords: list[str]) -> bool:
        return any(kw in text_lower for kw in keywords)

    def _extract_excerpt(self, text: str, keywords: list[str]) -> str:
        text_lower = text.lower()
        for kw in keywords:
            idx = text_lower.find(kw)
            if idx != -1:
                start = max(0, idx - 20)
                end = min(len(text), idx + len(kw) + 80)
                return text[start:end].strip()
        return text[:120]
