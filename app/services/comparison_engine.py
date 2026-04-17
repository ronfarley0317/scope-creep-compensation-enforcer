from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.contract import BillingRule, ContractScope
from app.models.creep_event import CreepEvent
from app.models.work_item import WorkItem


@dataclass(frozen=True)
class InScopeItem:
    work_item_id: str
    matched_scope_id: str
    matched_deliverable: str
    reason: str
    source_hours: float


@dataclass(frozen=True)
class OutOfScopeItem:
    work_item_id: str
    reason_code: str
    reason: str
    source_hours: float
    suggested_billable_basis: str


@dataclass(frozen=True)
class ExceededLimit:
    work_item_id: str
    limit_id: str
    limit_type: str
    allowed_value: float
    actual_value: float
    unit: str
    reason: str


@dataclass(frozen=True)
class RevenueImpactEstimate:
    currency: str
    estimated_amount: float | None
    pricing_basis: str
    pricing_confidence: str
    notes: str = ""


@dataclass(frozen=True)
class ComparisonResult:
    in_scope_items: list[InScopeItem] = field(default_factory=list)
    out_of_scope_items: list[OutOfScopeItem] = field(default_factory=list)
    exceeded_limits: list[ExceededLimit] = field(default_factory=list)
    revenue_impact_estimate: RevenueImpactEstimate | None = None
    creep_events: list[CreepEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "in_scope_items": [asdict(item) for item in self.in_scope_items],
            "out_of_scope_items": [asdict(item) for item in self.out_of_scope_items],
            "exceeded_limits": [asdict(item) for item in self.exceeded_limits],
            "revenue_impact_estimate": (
                asdict(self.revenue_impact_estimate) if self.revenue_impact_estimate else None
            ),
            "creep_events": [event.to_dict() for event in self.creep_events],
        }


class ComparisonEngine:
    """Compare normalized work items against config-driven contract scope."""

    def compare(self, contract: ContractScope, work_items: list[WorkItem]) -> ComparisonResult:
        interpretation = contract.interpretation
        revision_limit_type = interpretation.get("revision_limit_type", "revision_rounds")
        revision_billing_trigger = interpretation.get("revision_billing_trigger", "extra_revision_round")
        quantity_trigger_by_unit = interpretation.get("quantity_trigger_by_unit", {})
        out_of_scope_trigger = interpretation.get("out_of_scope_trigger", "out_of_scope")

        in_scope_items: list[InScopeItem] = []
        out_of_scope_items: list[OutOfScopeItem] = []
        exceeded_limits: list[ExceededLimit] = []
        creep_events: list[CreepEvent] = []

        tracked_quantities: dict[tuple[str, str], float] = {}

        for work_item in work_items:
            if contract.is_excluded(work_item.category):
                out_of_scope_items.append(
                    OutOfScopeItem(
                        work_item_id=work_item.id,
                        reason_code="excluded_category",
                        reason=f"Category '{work_item.category}' is excluded by contract config.",
                        source_hours=work_item.hours,
                        suggested_billable_basis=out_of_scope_trigger,
                    )
                )
                creep_events.append(
                    self._build_event(
                        contract,
                        work_item,
                        "out_of_scope",
                        f"Category '{work_item.category}' is excluded by config.",
                        work_item.deliverable_hint,
                        None,
                        "excluded_category",
                        None,
                        work_item.quantity,
                        work_item.quantity,
                        work_item.hours,
                        work_item.quantity,
                        work_item.quantity_unit,
                        contract.get_billing_rule(out_of_scope_trigger),
                    )
                )
                continue

            deliverable = contract.get_deliverable(work_item.deliverable_hint, work_item.category)
            if deliverable is None:
                out_of_scope_items.append(
                    OutOfScopeItem(
                        work_item_id=work_item.id,
                        reason_code="no_matching_deliverable",
                        reason="No deliverable mapping matched after config normalization.",
                        source_hours=work_item.hours,
                        suggested_billable_basis=out_of_scope_trigger,
                    )
                )
                creep_events.append(
                    self._build_event(
                        contract,
                        work_item,
                        "out_of_scope",
                        "No normalized deliverable matched this work item.",
                        work_item.deliverable_hint,
                        None,
                        "no_matching_deliverable",
                        None,
                        work_item.quantity,
                        work_item.quantity,
                        work_item.hours,
                        work_item.quantity,
                        work_item.quantity_unit,
                        contract.get_billing_rule(out_of_scope_trigger),
                    )
                )
                continue

            exceeded = False

            if work_item.quantity is not None and work_item.quantity_unit:
                quantity_key = (deliverable.id, work_item.quantity_unit)
                previous_total = tracked_quantities.get(quantity_key, 0.0)
                new_total = previous_total + work_item.quantity
                tracked_quantities[quantity_key] = new_total
                quantity_limit = deliverable.quantity_limits.get(work_item.quantity_unit)
                if quantity_limit is not None and new_total > quantity_limit:
                    trigger = quantity_trigger_by_unit.get(work_item.quantity_unit)
                    billing_rule = contract.get_billing_rule(trigger, deliverable.id) if trigger else None
                    overage_amount = max(0.0, new_total - quantity_limit) - max(0.0, previous_total - quantity_limit)
                    if overage_amount > 0:
                        exceeded = True
                        exceeded_limits.append(
                            ExceededLimit(
                                work_item_id=work_item.id,
                                limit_id=f"{deliverable.id}-{work_item.quantity_unit}",
                                limit_type=trigger or "quantity_overage",
                                allowed_value=quantity_limit,
                                actual_value=new_total,
                                unit=work_item.quantity_unit,
                                reason=f"Configured quantity limit exceeded for {deliverable.name}.",
                            )
                        )
                        creep_events.append(
                            self._build_event(
                                contract,
                                work_item,
                                trigger or "quantity_overage",
                                f"Configured quantity limit exceeded for deliverable '{deliverable.name}'.",
                                deliverable.name,
                                deliverable.id,
                                trigger or "quantity_overage",
                                quantity_limit,
                                new_total,
                                overage_amount,
                                None,
                                overage_amount,
                                work_item.quantity_unit,
                                billing_rule,
                            )
                        )

            if work_item.revision_number is not None:
                revision_limit = contract.get_limit(deliverable.id, revision_limit_type)
                if revision_limit is not None and work_item.revision_number > revision_limit.value:
                    exceeded = True
                    excess_rounds = work_item.revision_number - int(revision_limit.value)
                    billing_rule = contract.get_billing_rule(revision_billing_trigger, deliverable.id)
                    exceeded_limits.append(
                        ExceededLimit(
                            work_item_id=work_item.id,
                            limit_id=revision_limit.id,
                            limit_type=revision_limit_type,
                            allowed_value=revision_limit.value,
                            actual_value=work_item.revision_number,
                            unit=revision_limit.unit,
                            reason=f"Configured revision limit exceeded for {deliverable.name}.",
                        )
                    )
                    creep_events.append(
                        self._build_event(
                            contract,
                            work_item,
                            "limit_exceeded",
                            f"Configured revision limit exceeded for deliverable '{deliverable.name}'.",
                            deliverable.name,
                            deliverable.id,
                            "included_revisions_exceeded",
                            revision_limit.value,
                            float(work_item.revision_number),
                            float(excess_rounds),
                            None,
                            excess_rounds,
                            revision_limit.unit,
                            billing_rule,
                        )
                    )

            if not exceeded:
                in_scope_items.append(
                    InScopeItem(
                        work_item_id=work_item.id,
                        matched_scope_id=deliverable.id,
                        matched_deliverable=deliverable.name,
                        reason="Work item matches normalized scope and does not exceed config-defined limits.",
                        source_hours=work_item.hours,
                    )
                )

        return ComparisonResult(
            in_scope_items=in_scope_items,
            out_of_scope_items=out_of_scope_items,
            exceeded_limits=exceeded_limits,
            revenue_impact_estimate=self._build_revenue_estimate(contract, creep_events),
            creep_events=creep_events,
        )

    def _build_event(
        self,
        contract: ContractScope,
        work_item: WorkItem,
        event_type: str,
        reason: str,
        deliverable_name: str | None,
        scope_reference_id: str | None,
        rule_code: str,
        agreed_allowance: float | None,
        actual_delivered_amount: float | None,
        exceeded_amount: float | None,
        billable_hours: float | None,
        billable_quantity: float | None,
        billable_unit: str | None,
        billing_rule: BillingRule | None,
    ) -> CreepEvent:
        rate = billing_rule.rate if billing_rule else None
        estimated_amount = None
        if rate is not None:
            if billable_quantity is not None:
                estimated_amount = round(rate * billable_quantity, 2)
            elif billable_hours is not None:
                estimated_amount = round(rate * billable_hours, 2)
        revenue_impact_calculation = self._format_revenue_calculation(
            billable_quantity=billable_quantity,
            billable_hours=billable_hours,
            billable_unit=billable_unit,
            rate=rate,
            estimated_amount=estimated_amount,
        )
        system_explanation = self._format_system_explanation(
            normalized_category=work_item.category,
            agreed_allowance=agreed_allowance,
            actual_delivered_amount=actual_delivered_amount,
            exceeded_amount=exceeded_amount,
            unit=billable_unit,
            reason=reason,
            billing_rule=billing_rule,
        )
        client_explanation = self._format_client_explanation(
            deliverable_name=deliverable_name or work_item.deliverable_hint or work_item.category,
            agreed_allowance=agreed_allowance,
            actual_delivered_amount=actual_delivered_amount,
            exceeded_amount=exceeded_amount,
            unit=billable_unit,
            estimated_amount=estimated_amount,
            currency=(billing_rule.currency if billing_rule else contract.currency),
        )
        return CreepEvent(
            event_id=f"creep-{contract.client_id}-{work_item.id}",
            client_id=contract.client_id,
            work_item_id=work_item.id,
            event_type=event_type,
            normalized_category=work_item.category,
            source_type=work_item.source_type,
            source_reference=work_item.source_reference,
            source_excerpt=work_item.source_excerpt,
            reason=reason,
            scope_reference_id=scope_reference_id,
            rule_code=rule_code,
            agreed_allowance=agreed_allowance,
            actual_delivered_amount=actual_delivered_amount,
            exceeded_amount=exceeded_amount,
            billing_rule_applied=(billing_rule.id if billing_rule else None),
            revenue_impact_calculation=revenue_impact_calculation,
            system_explanation=system_explanation,
            client_explanation=client_explanation,
            billable_hours=billable_hours,
            billable_quantity=billable_quantity,
            billable_unit=billable_unit,
            rate=rate,
            estimated_amount=estimated_amount,
            currency=(billing_rule.currency if billing_rule else contract.currency),
        )

    def _format_revenue_calculation(
        self,
        *,
        billable_quantity: float | None,
        billable_hours: float | None,
        billable_unit: str | None,
        rate: float | None,
        estimated_amount: float | None,
    ) -> str:
        if rate is None or estimated_amount is None:
            return "No deterministic revenue calculation available."
        basis = billable_quantity if billable_quantity is not None else billable_hours
        unit = billable_unit or ("hours" if billable_hours is not None else "items")
        return f"{basis:g} x {rate:g} per {unit} = {estimated_amount:g}"

    def _format_system_explanation(
        self,
        *,
        normalized_category: str,
        agreed_allowance: float | None,
        actual_delivered_amount: float | None,
        exceeded_amount: float | None,
        unit: str | None,
        reason: str,
        billing_rule: BillingRule | None,
    ) -> str:
        if agreed_allowance is None or actual_delivered_amount is None or exceeded_amount is None:
            return (
                f"The normalized category '{normalized_category}' triggered scope creep. "
                f"{reason} Billing rule: {billing_rule.id if billing_rule else 'none'}."
            )
        unit_label = unit or "units"
        return (
            f"The normalized category '{normalized_category}' exceeded the agreed allowance of "
            f"{agreed_allowance:g} {unit_label} by delivering {actual_delivered_amount:g} {unit_label}, "
            f"which is {exceeded_amount:g} {unit_label} over the contract allowance. "
            f"Billing rule applied: {billing_rule.id if billing_rule else 'none'}."
        )

    def _format_client_explanation(
        self,
        *,
        deliverable_name: str,
        agreed_allowance: float | None,
        actual_delivered_amount: float | None,
        exceeded_amount: float | None,
        unit: str | None,
        estimated_amount: float | None,
        currency: str | None,
    ) -> str:
        item_label = self._humanize_deliverable_name(deliverable_name)
        unit_label = unit or "items"
        if (
            agreed_allowance is None
            or actual_delivered_amount is None
            or exceeded_amount is None
        ):
            if estimated_amount is None:
                return (
                    f"Additional work was completed for {item_label} beyond the agreed scope. "
                    "Pricing will need to be confirmed before any additional charge is issued."
                )
            return (
                f"Additional work was completed for {item_label} beyond the agreed scope. "
                f"This results in an additional charge of {currency} {estimated_amount:.2f}."
            )
        if estimated_amount is None:
            return (
                f"The project included {agreed_allowance:g} {unit_label} for {item_label}. "
                f"Work delivered exceeded that amount by {exceeded_amount:g} {unit_label}, for a total of {actual_delivered_amount:g} {unit_label}. "
                "Pricing will need to be confirmed before any additional charge is issued."
            )
        return (
            f"The project included {agreed_allowance:g} {unit_label} for {item_label}. "
            f"Work delivered exceeded that amount by {exceeded_amount:g} {unit_label}, for a total of {actual_delivered_amount:g} {unit_label}. "
            f"This results in an additional charge of {currency} {estimated_amount:.2f}."
        )

    def _humanize_deliverable_name(self, deliverable_name: str) -> str:
        return deliverable_name.replace("_", " ").replace("-", " ").strip().lower()

    def _build_revenue_estimate(
        self, contract: ContractScope, creep_events: list[CreepEvent]
    ) -> RevenueImpactEstimate:
        amounts = [event.estimated_amount for event in creep_events if event.estimated_amount is not None]
        if not creep_events:
            return RevenueImpactEstimate(
                currency=contract.currency,
                estimated_amount=0.0,
                pricing_basis="No scope-creep events detected.",
                pricing_confidence="high",
            )
        if len(amounts) != len(creep_events):
            return RevenueImpactEstimate(
                currency=contract.currency,
                estimated_amount=None,
                pricing_basis="At least one event lacks config-defined pricing.",
                pricing_confidence="low",
                notes="Review client billing rules.",
            )
        return RevenueImpactEstimate(
            currency=contract.currency,
            estimated_amount=round(sum(amounts), 2),
            pricing_basis="Sum of config-driven billable event estimates.",
            pricing_confidence="high",
        )
