from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.contract import ContractScope
from app.models.creep_event import CreepEvent
from app.models.invoice_item import InvoiceItem


@dataclass(frozen=True)
class CompensationResult:
    enforcement_mode: str
    compensation_type: str
    draft_invoice_line_items: list[InvoiceItem] = field(default_factory=list)
    draft_change_order_summary: dict[str, Any] | None = None
    internal_approval_note: dict[str, Any] = field(default_factory=dict)
    client_facing_summary: dict[str, Any] = field(default_factory=dict)
    human_readable_draft: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enforcement_mode": self.enforcement_mode,
            "compensation_type": self.compensation_type,
            "draft_invoice_line_items": [item.to_dict() for item in self.draft_invoice_line_items],
            "draft_change_order_summary": self.draft_change_order_summary,
            "internal_approval_note": self.internal_approval_note,
            "client_facing_summary": self.client_facing_summary,
            "human_readable_draft": self.human_readable_draft,
        }


class CompensationEngine:
    """Build draft compensation artifacts from validated scope-creep events."""

    def build(
        self,
        contract: ContractScope,
        creep_events: list[CreepEvent],
        enforcement_mode: str = "recommend",
    ) -> CompensationResult:
        enforcement_mode = self._normalize_enforcement_mode(enforcement_mode)
        labels = contract.interpretation.get("compensation_labels", {})
        compensation_type = self._choose_compensation_type(creep_events)
        invoice_items = self._build_invoice_items(contract, creep_events)
        change_order_summary = self._build_change_order_summary(
            creep_events, compensation_type, enforcement_mode
        )
        internal_note = self._build_internal_note(
            creep_events, compensation_type, labels, enforcement_mode
        )
        client_summary = self._build_client_summary(
            contract, creep_events, compensation_type, labels, enforcement_mode
        )
        human_readable_draft = self._build_human_readable_draft(
            internal_note=internal_note,
            client_summary=client_summary,
        )

        return CompensationResult(
            enforcement_mode=enforcement_mode,
            compensation_type=compensation_type,
            draft_invoice_line_items=invoice_items,
            draft_change_order_summary=change_order_summary,
            internal_approval_note=internal_note,
            client_facing_summary=client_summary,
            human_readable_draft=human_readable_draft,
        )

    def _choose_compensation_type(self, creep_events: list[CreepEvent]) -> str:
        if not creep_events:
            return "approval_request"

        priced = [event for event in creep_events if event.estimated_amount is not None]
        unpriced = [event for event in creep_events if event.estimated_amount is None]

        if priced and unpriced:
            return "mixed"
        if unpriced:
            if any(event.event_type == "out_of_scope" for event in creep_events):
                return "change_order"
            return "approval_request"
        return "invoice_line_item"

    def _build_invoice_items(
        self, contract: ContractScope, creep_events: list[CreepEvent]
    ) -> list[InvoiceItem]:
        items: list[InvoiceItem] = []
        for index, event in enumerate(creep_events, start=1):
            if event.estimated_amount is None:
                continue
            if event.billable_quantity is not None:
                quantity = event.billable_quantity
                unit = event.billable_unit or "item"
            elif event.billable_hours is not None:
                quantity = event.billable_hours
                unit = "hours"
            else:
                quantity = 1.0
                unit = "item"
            items.append(
                InvoiceItem(
                    id=f"invoice_item_{index}",
                    client_id=contract.client_id,
                    event_id=event.event_id,
                    description=event.reason,
                    quantity=quantity,
                    unit=unit,
                    rate=event.rate,
                    amount=event.estimated_amount,
                    currency=event.currency or contract.currency,
                )
            )
        return items

    def _build_change_order_summary(
        self, creep_events: list[CreepEvent], compensation_type: str, enforcement_mode: str
    ) -> dict[str, Any] | None:
        if compensation_type not in {"change_order", "mixed"}:
            return None

        total_known_amount = round(
            sum(event.estimated_amount or 0.0 for event in creep_events), 2
        )
        return {
            "title": "Draft change order for validated scope-creep work",
            "scope_change_summary": "Validated work extends beyond the original statement of work and requires formal review.",
            "related_event_ids": [event.event_id for event in creep_events],
            "pricing_summary": (
                f"Known priced impact: {total_known_amount:.2f}; additional pricing may require approval."
            ),
            "schedule_impact": "No automatic schedule change assumed in MVP output.",
            "approval_required": True,
            "action_to_take": self._change_order_action(compensation_type, enforcement_mode),
        }

    def _build_internal_note(
        self,
        creep_events: list[CreepEvent],
        compensation_type: str,
        labels: dict[str, Any],
        enforcement_mode: str,
    ) -> dict[str, Any]:
        known_amount = round(sum(event.estimated_amount or 0.0 for event in creep_events), 2)
        missing_pricing = [event.event_id for event in creep_events if event.estimated_amount is None]
        return {
            "summary": labels.get(
                "internal_summary",
                f"{len(creep_events)} validated scope-creep event(s) prepared for compensation handling.",
            ),
            "enforcement_mode": enforcement_mode,
            "recommended_action": self._recommended_action(compensation_type, enforcement_mode),
            "action_to_take": self._internal_action_to_take(compensation_type, enforcement_mode),
            "risks": [
                "Confirm client pre-approval requirements before issuing final billing."
            ],
            "missing_information": (
                [f"Pricing requires review for event(s): {', '.join(missing_pricing)}"]
                if missing_pricing
                else []
            ),
            "known_estimated_amount": known_amount,
        }

    def _build_client_summary(
        self,
        contract: ContractScope,
        creep_events: list[CreepEvent],
        compensation_type: str,
        labels: dict[str, Any],
        enforcement_mode: str,
    ) -> dict[str, Any]:
        known_amount = round(sum(event.estimated_amount or 0.0 for event in creep_events), 2)
        pricing_statement = (
            f"Known priced impact totals {known_amount:.2f} {contract.currency}."
            if any(event.estimated_amount is not None for event in creep_events)
            else "Pricing requires review against the contract before billing."
        )
        return {
            "enforcement_mode": enforcement_mode,
            "summary": self._client_summary_text(
                labels=labels,
                creep_events=creep_events,
                compensation_type=compensation_type,
                enforcement_mode=enforcement_mode,
            ),
            "requested_action": self._requested_action(compensation_type, enforcement_mode),
            "action_to_take": self._client_action_to_take(compensation_type, enforcement_mode),
            "pricing_statement": pricing_statement,
            "timeline_statement": "No schedule change is assumed in this draft.",
        }

    def _build_human_readable_draft(
        self, internal_note: dict[str, Any], client_summary: dict[str, Any]
    ) -> str:
        return (
            "Internal Draft\n"
            f"{internal_note['summary']} {internal_note['recommended_action']} "
            f"Action: {internal_note['action_to_take']} "
            f"Risks: {', '.join(internal_note['risks'])}\n\n"
            "Client Draft\n"
            f"{client_summary['summary']} {client_summary['requested_action']} "
            f"Action: {client_summary['action_to_take']} "
            f"{client_summary['pricing_statement']} {client_summary['timeline_statement']}"
        )

    def _recommended_action(self, compensation_type: str, enforcement_mode: str) -> str:
        mapping = {
            "suggest": {
                "invoice_line_item": "Suggest draft invoice items for optional review before billing.",
                "change_order": "Suggest a change order for review before any billing action.",
                "approval_request": "Suggest an approval review before creating billing artifacts.",
                "mixed": "Suggest review of priced items and change-order escalation for the remainder.",
            },
            "recommend": {
                "invoice_line_item": "These items are recommended for inclusion in the upcoming invoice.",
                "change_order": "Recommend preparing a change order for client approval before invoicing.",
                "approval_request": "Recommend requesting approval before creating billing artifacts.",
                "mixed": "Recommend approving priced items and escalating unpriced items for change-order review.",
            },
            "enforce": {
                "invoice_line_item": "Proceed with including draft invoice items in the next billing cycle.",
                "change_order": "Issue a change order immediately and block billing until it is accepted.",
                "approval_request": "Escalate immediately and hold billing until approval is recorded.",
                "mixed": "Include priced items automatically and escalate unpriced items for mandatory review.",
            },
        }
        return mapping[enforcement_mode][compensation_type]

    def _requested_action(self, compensation_type: str, enforcement_mode: str) -> str:
        mapping = {
            "suggest": {
                "invoice_line_item": "We suggest reviewing these items for possible inclusion on a future invoice.",
                "change_order": "We suggest reviewing the proposed scope change before any billing proceeds.",
                "approval_request": "We suggest reviewing the identified work before compensation handling proceeds.",
                "mixed": "We suggest reviewing the priced items and the remaining scope changes before follow-up billing.",
            },
            "recommend": {
                "invoice_line_item": "These items are recommended for inclusion in the upcoming invoice.",
                "change_order": "Please review and approve the proposed scope change before billing proceeds.",
                "approval_request": "Please review the identified work and confirm approval for compensation handling.",
                "mixed": "Please review the priced items and approve the remaining scope changes for follow-up billing.",
            },
            "enforce": {
                "invoice_line_item": "These items are scheduled for inclusion on the upcoming invoice.",
                "change_order": "This scope change requires immediate approval before billing can continue.",
                "approval_request": "This work requires immediate approval before compensation handling can continue.",
                "mixed": "Priced items will be billed automatically while remaining scope changes require immediate review.",
            },
        }
        return mapping[enforcement_mode][compensation_type]

    def _internal_action_to_take(self, compensation_type: str, enforcement_mode: str) -> str:
        mapping = {
            "suggest": {
                "invoice_line_item": "Hold invoice inclusion pending optional finance review.",
                "change_order": "Draft the change order and wait for internal confirmation before sending.",
                "approval_request": "Queue approval review and pause billing artifact creation.",
                "mixed": "Pause priced items for optional review and escalate unpriced items for clarification.",
            },
            "recommend": {
                "invoice_line_item": "Include these items in the upcoming invoice. Flag for review if needed.",
                "change_order": "Prepare and send the change order for approval before invoicing.",
                "approval_request": "Send an approval request and wait for a recorded decision before billing.",
                "mixed": "Approve priced items through standard billing review and escalate the remaining items for change-order handling.",
            },
            "enforce": {
                "invoice_line_item": "Mark invoice items for automatic inclusion in the next invoice run.",
                "change_order": "Send the change order immediately and suspend billing until client acceptance is logged.",
                "approval_request": "Escalate for immediate approval and block downstream billing until resolved.",
                "mixed": "Auto-include priced items in billing and require immediate resolution of unpriced items.",
            },
        }
        return mapping[enforcement_mode][compensation_type]

    def _client_action_to_take(self, compensation_type: str, enforcement_mode: str) -> str:
        mapping = {
            "suggest": {
                "invoice_line_item": "Action to be taken: review these items and confirm whether you want them added to a future invoice.",
                "change_order": "Action to be taken: review the proposed scope change and confirm whether you want to proceed.",
                "approval_request": "Action to be taken: review the identified work and confirm how you want us to handle compensation.",
                "mixed": "Action to be taken: review the priced items and confirm how the remaining scope changes should be handled.",
            },
            "recommend": {
                "invoice_line_item": "Action to be taken: include these items in the upcoming invoice. Flag for review if needed.",
                "change_order": "Action to be taken: approve the scope change so billing can proceed.",
                "approval_request": "Action to be taken: confirm approval so compensation handling can proceed.",
                "mixed": "Action to be taken: approve the priced items and confirm how the remaining scope changes should be billed.",
            },
            "enforce": {
                "invoice_line_item": "Action to be taken: these items will be included automatically on the upcoming invoice.",
                "change_order": "Action to be taken: approve the scope change immediately to avoid blocking billing.",
                "approval_request": "Action to be taken: provide immediate approval to avoid blocking compensation handling.",
                "mixed": "Action to be taken: priced items will be billed automatically and the remaining scope changes require immediate approval.",
            },
        }
        return mapping[enforcement_mode][compensation_type]

    def _client_summary_text(
        self,
        *,
        labels: dict[str, Any],
        creep_events: list[CreepEvent],
        compensation_type: str,
        enforcement_mode: str,
    ) -> str:
        if "client_summary" in labels and enforcement_mode == "recommend":
            return labels["client_summary"]
        tone = {
            "suggest": "We found work that appears to fall outside the original scope and suggest reviewing it before billing.",
            "recommend": f"We identified {len(creep_events)} completed work item(s) that fall outside the original scope or exceeded agreed limits.",
            "enforce": "We identified completed work outside the agreed scope and will apply the configured compensation handling automatically unless blocked.",
        }
        if compensation_type == "change_order" and enforcement_mode == "enforce":
            return "We identified work outside the agreed scope that requires immediate change-order approval before billing can continue."
        return tone[enforcement_mode]

    def _change_order_action(self, compensation_type: str, enforcement_mode: str) -> str:
        if compensation_type not in {"change_order", "mixed"}:
            return "No change-order action required."
        mapping = {
            "suggest": "Prepare the change order draft for optional review.",
            "recommend": "Prepare and send the change order for approval.",
            "enforce": "Send the change order immediately and block billing until approved.",
        }
        return mapping[enforcement_mode]

    def _normalize_enforcement_mode(self, enforcement_mode: str) -> str:
        supported = {"suggest", "recommend", "enforce"}
        normalized = enforcement_mode.strip().lower()
        if normalized not in supported:
            return "recommend"
        return normalized
