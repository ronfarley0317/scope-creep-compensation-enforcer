from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.run_metadata import RunMetadata
from app.services.comparison_engine import ComparisonEngine
from app.services.compensation_engine import CompensationEngine
from app.services.config_loader import load_client_bundle
from app.services.delivery_artifact_generator import DeliveryArtifactGenerator
from app.services.invoice_artifact_generator import InvoiceArtifactGenerator
from app.services.scope_normalizer import ScopeNormalizer
from app.sources.resolver import SourceResolver


def run_single_client(client_dir: str | Path) -> dict[str, Any]:
    base_path = Path(client_dir)
    run_id = _generate_run_id()
    started_at = datetime.now()
    client_name = base_path.name
    output_paths: dict[str, str] = {}
    run_history_dir = Path("outputs/run_history").resolve()
    source_lane_types = {
        "scope_source_type": "unknown",
        "work_source_type": "unknown",
        "billing_source_type": "unknown",
    }

    try:
        bundle = load_client_bundle(base_path)
        client_config = {**bundle.client, "_client_dir": str(base_path)}
        client_name = client_config.get("client_name", client_name)
        source_lane_types = {
            "scope_source_type": client_config.get("scope_source_type", "unknown"),
            "work_source_type": client_config.get("work_source_type", "unknown"),
            "billing_source_type": client_config.get("billing_source_type", "unknown"),
        }
        output_dir = _resolve_path(base_path, bundle.client["output_dir"])
        run_history_dir = output_dir.parent / "run_history"
        normalizer = ScopeNormalizer(client_config, bundle.contract_rules, bundle.field_mapping)

        source_resolver = SourceResolver()
        source_lanes = source_resolver.resolve_lanes(client_config)
        scope_adapter = source_lanes["scope_adapter"]
        work_adapter = source_lanes["work_adapter"]
        billing_adapter = source_lanes["billing_adapter"]
        scope_input = scope_adapter.fetch_scope_inputs(client_config)
        work_activity_input = work_adapter.fetch_work_activity_inputs(client_config)

        contract = normalizer.normalize_contract(scope_input)
        work_items = normalizer.normalize_work_log(work_activity_input)

        comparison_result = ComparisonEngine().compare(contract, work_items)
        enforcement_mode = (
            bundle.client.get("default_outputs", {}).get("compensation_enforcement_mode", "recommend")
        )
        compensation_result = CompensationEngine().build(
            contract,
            comparison_result.creep_events,
            enforcement_mode=enforcement_mode,
        )
        invoice_date = _resolve_invoice_date(work_activity_input.payload)
        invoice_artifact = InvoiceArtifactGenerator().build(
            contract,
            comparison_result.creep_events,
            invoice_date=invoice_date,
        )
        invoice_file_refs = _invoice_output_paths(output_dir.parent / "invoices", client_config["client_id"])
        billing_artifact = billing_adapter.prepare_billing_package(
            client_config,
            {
                "invoice_json": invoice_artifact.invoice_json,
                "invoice_markdown": invoice_artifact.invoice_markdown,
            },
            compensation_result.to_dict(),
            invoice_file_refs,
        )

        output_payload = {
            "run_id": run_id,
            "client": client_config,
            "contract_rules": bundle.contract_rules,
            "field_mapping": bundle.field_mapping,
            "scope_input": scope_input.to_dict(),
            "work_activity_input": work_activity_input.to_dict(),
            "raw_contract": scope_input.payload,
            "raw_work_log": work_activity_input.payload,
            "normalized_contract": contract.to_dict(),
            "normalized_work_items": [item.to_dict() for item in work_items],
            "comparison": comparison_result.to_dict(),
            "compensation": compensation_result.to_dict(),
            "invoice_artifacts": {
                "invoice_json": invoice_artifact.invoice_json,
                "invoice_markdown": invoice_artifact.invoice_markdown,
            },
            "billing_artifacts": billing_artifact,
            "source_lanes": {
                "scope_source_type": source_lanes["scope_source_type"],
                "work_source_type": source_lanes["work_source_type"],
                "billing_source_type": source_lanes["billing_source_type"],
            },
            "source_healthcheck": {
                "scope": scope_adapter.healthcheck(client_config),
                "work": work_adapter.healthcheck(client_config),
                "billing": billing_adapter.healthcheck(client_config),
            },
        }
        output_payload["overdelivery_summary"] = build_overdelivery_summary(output_payload)
        output_payload["revenue_leakage_projection"] = build_revenue_leakage_projection(output_payload)

        output_paths = _write_outputs(output_dir, output_payload, billing_adapter)
        output_payload["output_paths"] = output_paths
        output_payload["terminal_summary"] = build_terminal_summary(output_payload)
        markdown_summary = build_markdown_summary(output_payload)
        output_payload["markdown_summary"] = markdown_summary
        client_report = build_client_report(output_payload)
        output_payload["client_report"] = client_report
        Path(output_paths["markdown_summary"]).write_text(markdown_summary, encoding="utf-8")
        Path(output_paths["client_report"]).write_text(client_report, encoding="utf-8")
        delivery_artifact = DeliveryArtifactGenerator().build(output_payload, output_paths)
        delivery_paths = _write_delivery_artifacts(output_dir.parent / "delivery", output_payload, delivery_artifact)
        output_paths.update(delivery_paths)
        output_payload["delivery_artifacts"] = {
            "delivery_package_json": delivery_artifact.package_json,
            "delivery_summary_markdown": delivery_artifact.summary_markdown,
        }

        run_metadata = RunMetadata(
            run_id=run_id,
            client_name=client_name,
            started_at=started_at.isoformat(timespec="seconds"),
            completed_at=datetime.now().isoformat(timespec="seconds"),
            status="success",
            scope_source_type=source_lane_types["scope_source_type"],
            work_source_type=source_lane_types["work_source_type"],
            billing_source_type=source_lane_types["billing_source_type"],
            total_scope_creep_events=len(output_payload["comparison"]["creep_events"]),
            total_billable_impact=float(
                output_payload["comparison"]["revenue_impact_estimate"]["estimated_amount"] or 0.0
            ),
            generated_artifacts=dict(output_paths),
            error_message=None,
        )
        run_history_path = _write_run_history(run_history_dir, run_metadata)
        output_paths["run_history"] = run_history_path
        output_payload["run_history"] = run_metadata.to_dict()
        output_payload["output_paths"] = output_paths
        Path(output_paths["run_summary"]).write_text(
            json.dumps(output_payload, indent=2), encoding="utf-8"
        )
        return output_payload
    except Exception as exc:
        run_metadata = RunMetadata(
            run_id=run_id,
            client_name=client_name,
            started_at=started_at.isoformat(timespec="seconds"),
            completed_at=datetime.now().isoformat(timespec="seconds"),
            status="failure",
            scope_source_type=source_lane_types["scope_source_type"],
            work_source_type=source_lane_types["work_source_type"],
            billing_source_type=source_lane_types["billing_source_type"],
            total_scope_creep_events=0,
            total_billable_impact=0.0,
            generated_artifacts=dict(output_paths),
            error_message=str(exc),
        )
        _write_run_history(run_history_dir, run_metadata)
        raise


def build_terminal_summary(run_result: dict[str, Any]) -> str:
    client = run_result["client"]
    comparison = run_result["comparison"]
    compensation = run_result["compensation"]
    revenue = comparison["revenue_impact_estimate"]
    return "\n".join(
        [
            f"Client: {client['client_name']} ({client['client_id']})",
            f"Normalized work items: {len(run_result['normalized_work_items'])}",
            f"In-scope items: {len(comparison['in_scope_items'])}",
            f"Out-of-scope items: {len(comparison['out_of_scope_items'])}",
            f"Exceeded limits: {len(comparison['exceeded_limits'])}",
            f"Scope-creep events: {len(comparison['creep_events'])}",
            (
                f"Estimated billable amount: {revenue['currency']} {revenue['estimated_amount']:.2f}"
                if revenue and revenue["estimated_amount"] is not None
                else "Estimated billable amount: requires review"
            ),
            f"Compensation type: {compensation['compensation_type']}",
            f"Draft invoice items: {len(compensation['draft_invoice_line_items'])}",
            f"Outputs written to: {run_result['output_paths']['output_dir']}",
        ]
    )


def main() -> None:
    result = run_single_client(Path("configs/clients/demo-client"))
    print(result["terminal_summary"])


def _generate_run_id() -> str:
    return f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _write_run_history(run_history_dir: Path, run_metadata: RunMetadata) -> str:
    run_history_dir.mkdir(parents=True, exist_ok=True)
    path = run_history_dir / f"{run_metadata.run_id}.json"
    path.write_text(json.dumps(run_metadata.to_dict(), indent=2), encoding="utf-8")
    return str(path)


def build_markdown_summary(run_result: dict[str, Any]) -> str:
    comparison = run_result["comparison"]
    compensation = run_result["compensation"]
    lines = [
        "# Demo Client Scope Creep Summary",
        "",
        f"- Client: {run_result['client']['client_name']} (`{run_result['client']['client_id']}`)",
        f"- Scope-creep events: {len(comparison['creep_events'])}",
        f"- Estimated billable amount: {comparison['revenue_impact_estimate']['currency']} {comparison['revenue_impact_estimate']['estimated_amount']:.2f}",
        f"- Compensation type: {compensation['compensation_type']}",
        "",
        "## Decision Trace",
        "",
    ]
    for event in comparison["creep_events"]:
        lines.extend(
            [
                f"### {event['event_id']}",
                f"- Category: `{event['normalized_category']}`",
                f"- Agreed allowance: {event['agreed_allowance']}",
                f"- Actual delivered amount: {event['actual_delivered_amount']}",
                f"- Exceeded amount: {event['exceeded_amount']}",
                f"- Billing rule applied: `{event['billing_rule_applied']}`",
                f"- Source type: `{event['source_type']}`",
                f"- Source reference: `{event['source_reference']}`",
                f"- Source excerpt: {event['source_excerpt']}",
                f"- Revenue impact calculation: `{event['revenue_impact_calculation']}`",
                f"- System explanation: {event['system_explanation']}",
                f"- Client explanation: {event['client_explanation']}",
                "",
            ]
        )
    return "\n".join(lines)


def build_client_report(run_result: dict[str, Any]) -> str:
    client = run_result["client"]
    comparison = run_result["comparison"]
    compensation = run_result["compensation"]
    revenue = comparison["revenue_impact_estimate"]
    overdelivery = run_result["overdelivery_summary"]
    leakage = run_result["revenue_leakage_projection"]
    total_amount = revenue["estimated_amount"]
    currency = revenue["currency"]

    event_lines = []
    for index, event in enumerate(comparison["creep_events"], start=1):
        event_lines.extend(
            [
                f"### Event {index}",
                f"- Event ID: `{event['event_id']}`",
                f"- Summary: {event['client_explanation']}",
                f"- Agreed scope amount: {event['agreed_allowance']}",
                f"- Delivered amount: {event['actual_delivered_amount']}",
                f"- Additional amount beyond scope: {event['exceeded_amount']}",
                f"- Source reference: `{event['source_type']}` / `{event['source_reference']}`",
                f"- Source excerpt: {event['source_excerpt']}",
                "",
            ]
        )

    revenue_lines = [
        f"- Estimated total revenue impact: {currency} {total_amount:.2f}",
        f"- Pricing basis: {revenue['pricing_basis']}",
        f"- Pricing confidence: {revenue['pricing_confidence']}",
    ]
    if revenue.get("notes"):
        revenue_lines.append(f"- Notes: {revenue['notes']}")

    compensation_lines = [
        f"- Compensation type: `{compensation['compensation_type']}`",
        f"- Client-facing recommendation: {compensation['client_facing_summary']['requested_action']}",
    ]
    for item in compensation["draft_invoice_line_items"]:
        compensation_lines.append(
            f"- Draft invoice item `{item['id']}`: {item['quantity']:g} {item['unit']} x {item['rate']:g} = {item['currency']} {item['amount']:.2f}"
        )

    assumption_lines = [f"- {assumption}" for assumption in run_result["contract_rules"]["assumptions"]]
    assumption_lines.extend(
        [
            "- This report is generated from normalized SOW and work-log inputs using deterministic contract rules.",
            "- The audit trace below maps each compensation recommendation to a specific normalized event.",
        ]
    )

    leakage_projection = _format_currency(leakage["projected_monthly_leakage"], currency)
    recovery_low = _format_currency(leakage["recovery_opportunity_min"], currency)
    recovery_high = _format_currency(leakage["recovery_opportunity_max"], currency)

    table_lines = [
        "| Event ID | Category | Allowance | Actual | Exceeded | Source | Source Excerpt | Billing Rule | Revenue Calculation |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for event in comparison["creep_events"]:
        table_lines.append(
            f"| `{event['event_id']}` | `{event['normalized_category']}` | {event['agreed_allowance']} | {event['actual_delivered_amount']} | {event['exceeded_amount']} | `{event['source_type']}` / `{event['source_reference']}` | {event['source_excerpt']} | `{event['billing_rule_applied']}` | `{event['revenue_impact_calculation']}` |"
        )

    lines = [
        f"# Scope Creep Report: {client['client_name']}",
        "",
        "## Executive Summary",
        (
            f"The demo workflow identified {len(comparison['creep_events'])} scope-creep event(s) for "
            f"{client['client_name']}. Based on the configured contract rules, the current estimated "
            f"billable impact is {currency} {total_amount:.2f}."
        ),
        (
            f"Overall, this reflects a {overdelivery['overall_overdelivery_percent']:.1f}% over-delivery "
            "against the agreed scope tracked in this reporting period."
            if overdelivery["overall_overdelivery_percent"] is not None
            else "Overall over-delivery could not be calculated from the available scope quantities."
        ),
        *[
            f"- {item['insight']}"
            for item in overdelivery["category_insights"]
        ],
        "",
        "## Scope-Creep Events Detected",
        *event_lines,
        "## Revenue Impact",
        *revenue_lines,
        "",
        "## Estimated Monthly Revenue Leakage",
        (
            "Based on current activity patterns, projected monthly leakage is "
            f"approximately {leakage_projection}."
        ),
        f"- Methodology: {leakage['methodology_explanation']}",
        f"- Confidence level: {leakage['confidence_level']}",
        "",
        "## Recovery Opportunity",
        (
            "If similar patterns persist, implementing automated enforcement could recover "
            f"{recovery_low}-{recovery_high} per month."
        ),
        f"- Recovery basis: {leakage['recovery_explanation']}",
        "",
        "## Enforcement Impact",
        "- Without Enforcement:",
        "Additional work completed without compensation",
        "- With Enforcement:",
        f"{_format_currency(total_amount, currency)} captured and billed",
        "- Net Impact:",
        f"+ {_format_currency(total_amount, currency)} recovered revenue",
        "",
        "## Recommended Compensation Actions",
        *compensation_lines,
        "",
        "## Assumptions and Notes",
        *assumption_lines,
        "",
        "## Audit Trace Table",
        *table_lines,
        "",
    ]
    return "\n".join(lines)


def _format_currency(amount: float | None, currency: str) -> str:
    if amount is None:
        return f"{currency} 0.00"
    return f"{currency} {amount:.2f}"


def build_overdelivery_summary(run_result: dict[str, Any]) -> dict[str, Any]:
    events = run_result["comparison"]["creep_events"]
    by_category: dict[str, dict[str, float]] = {}
    total_allowance = 0.0
    total_actual = 0.0

    for event in events:
        allowance = event.get("agreed_allowance")
        actual = event.get("actual_delivered_amount")
        if allowance in (None, 0) or actual is None:
            continue
        category = event["normalized_category"]
        bucket = by_category.setdefault(
            category,
            {"agreed_allowance": 0.0, "actual_delivered_amount": 0.0},
        )
        bucket["agreed_allowance"] += float(allowance)
        bucket["actual_delivered_amount"] += float(actual)
        total_allowance += float(allowance)
        total_actual += float(actual)

    category_insights: list[dict[str, Any]] = []
    for category, values in by_category.items():
        allowance = values["agreed_allowance"]
        actual = values["actual_delivered_amount"]
        overdelivery_percent = round(((actual - allowance) / allowance) * 100, 1)
        label = category.replace("_", " ")
        insight = (
            f"This represents a {overdelivery_percent:.1f}% over-delivery on {label} work "
            f"({actual:g} delivered versus {allowance:g} agreed)."
        )
        category_insights.append(
            {
                "category": category,
                "agreed_allowance": allowance,
                "actual_delivered_amount": actual,
                "overdelivery_percent": overdelivery_percent,
                "insight": insight,
            }
        )

    category_insights.sort(key=lambda item: item["overdelivery_percent"], reverse=True)
    overall_percent = None
    if total_allowance > 0:
        overall_percent = round(((total_actual - total_allowance) / total_allowance) * 100, 1)

    return {
        "overall_agreed_allowance": total_allowance,
        "overall_actual_delivered_amount": total_actual,
        "overall_overdelivery_percent": overall_percent,
        "category_insights": category_insights,
    }


def build_revenue_leakage_projection(run_result: dict[str, Any]) -> dict[str, Any]:
    raw_work_log = run_result["raw_work_log"]
    comparison = run_result["comparison"]
    currency = comparison["revenue_impact_estimate"]["currency"]
    total_amount = comparison["revenue_impact_estimate"]["estimated_amount"] or 0.0
    creep_event_count = len(comparison["creep_events"])

    start_date, end_date = _resolve_period_dates(raw_work_log, run_result["normalized_work_items"])
    span_days = max(1, (end_date - start_date).days + 1)

    if span_days >= 21:
        weekly_rate = total_amount / (span_days / 7)
        projected_monthly = round(weekly_rate * 4.345, 2)
        cadence = "weekly"
        methodology = (
            f"Calculated from {creep_event_count} scope-creep event(s) across {span_days} days "
            f"using a weekly leakage rate of {currency} {weekly_rate:.2f}, extrapolated over 4.345 weeks."
        )
    else:
        daily_rate = total_amount / span_days
        projected_monthly = round(daily_rate * 30, 2)
        cadence = "daily"
        methodology = (
            f"Calculated from {creep_event_count} scope-creep event(s) across {span_days} days "
            f"using a daily leakage rate of {currency} {daily_rate:.2f}, extrapolated over 30 days."
        )

    confidence = _projection_confidence(creep_event_count, span_days)
    recovery_min_multiplier, recovery_max_multiplier = _recovery_band(confidence)
    recovery_min = round(projected_monthly * recovery_min_multiplier, 2)
    recovery_max = round(projected_monthly * recovery_max_multiplier, 2)

    return {
        "currency": currency,
        "event_count": creep_event_count,
        "observation_start_date": start_date.isoformat(),
        "observation_end_date": end_date.isoformat(),
        "observation_span_days": span_days,
        "projection_cadence": cadence,
        "projected_monthly_leakage": projected_monthly,
        "methodology_explanation": methodology,
        "confidence_level": confidence,
        "recovery_opportunity_min": recovery_min,
        "recovery_opportunity_max": recovery_max,
        "recovery_explanation": (
            f"Recovery range applies a {recovery_min_multiplier:.0%}-{recovery_max_multiplier:.0%} "
            f"capture band based on {confidence} confidence in the observed pattern."
        ),
    }


def _resolve_period_dates(raw_work_log: dict[str, Any], normalized_work_items: list[dict[str, Any]]) -> tuple[date, date]:
    period = raw_work_log.get("period", {})
    start_date_value = period.get("start_date")
    end_date_value = period.get("end_date")
    if start_date_value and end_date_value:
        return date.fromisoformat(start_date_value), date.fromisoformat(end_date_value)

    performed_dates = [
        item["performed_on"]
        for item in normalized_work_items
        if item.get("performed_on")
    ]
    if not performed_dates:
        today = date.today()
        return today, today
    parsed = sorted(date.fromisoformat(value) for value in performed_dates)
    return parsed[0], parsed[-1]


def _projection_confidence(creep_event_count: int, span_days: int) -> str:
    if creep_event_count >= 3 and span_days >= 21:
        return "high"
    if creep_event_count >= 2 and span_days >= 7:
        return "medium"
    return "low"


def _recovery_band(confidence: str) -> tuple[float, float]:
    bands = {
        "high": (0.85, 1.0),
        "medium": (0.65, 0.9),
        "low": (0.4, 0.75),
    }
    return bands[confidence]


def _write_outputs(output_dir: Path, output_payload: dict[str, Any], billing_adapter: Any) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = output_dir / "comparison.json"
    compensation_path = output_dir / "compensation.json"
    run_summary_path = output_dir / "run_summary.json"
    markdown_summary_path = output_dir / "summary.md"
    report_dir = output_dir.parent / "reports"
    report_path = report_dir / "demo-client-scope-creep-report.md"
    invoice_dir = output_dir.parent / "invoices"
    billing_dir = output_dir.parent / "billing"
    comparison_path.write_text(json.dumps(output_payload["comparison"], indent=2), encoding="utf-8")
    compensation_path.write_text(json.dumps(output_payload["compensation"], indent=2), encoding="utf-8")
    report_dir.mkdir(parents=True, exist_ok=True)
    invoice_paths = _write_invoice_artifacts(invoice_dir, output_payload)
    billing_paths = _write_billing_artifacts(billing_dir, output_payload, billing_adapter)
    return {
        "output_dir": str(output_dir),
        "comparison": str(comparison_path),
        "compensation": str(compensation_path),
        "run_summary": str(run_summary_path),
        "markdown_summary": str(markdown_summary_path),
        "client_report": str(report_path),
        "invoice_json": invoice_paths["invoice_json"],
        "invoice_markdown": invoice_paths["invoice_markdown"],
        "billing_package_json": billing_paths["billing_package_json"],
        "billing_cover_markdown": billing_paths["billing_cover_markdown"],
    }


def _invoice_output_paths(output_dir: Path, client_slug: str) -> dict[str, str]:
    return {
        "invoice_json": str(output_dir / f"{client_slug}-invoice.json"),
        "invoice_markdown": str(output_dir / f"{client_slug}-invoice.md"),
    }


def _write_invoice_artifacts(output_dir: Path, output_payload: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    client_slug = output_payload["client"]["client_id"]
    invoice_paths = _invoice_output_paths(output_dir, client_slug)
    invoice_json_path = Path(invoice_paths["invoice_json"])
    invoice_markdown_path = Path(invoice_paths["invoice_markdown"])
    invoice_json_path.write_text(
        json.dumps(output_payload["invoice_artifacts"]["invoice_json"], indent=2),
        encoding="utf-8",
    )
    invoice_markdown_path.write_text(
        output_payload["invoice_artifacts"]["invoice_markdown"],
        encoding="utf-8",
    )
    return {
        "invoice_json": str(invoice_json_path),
        "invoice_markdown": str(invoice_markdown_path),
    }


def _write_billing_artifacts(
    output_dir: Path,
    output_payload: dict[str, Any],
    billing_adapter: Any,
) -> dict[str, str]:
    client_slug = output_payload["client"]["client_id"]
    return billing_adapter.write(output_dir, client_slug, output_payload["billing_artifacts"])


def _write_delivery_artifacts(
    output_dir: Path,
    output_payload: dict[str, Any],
    delivery_artifact: Any,
) -> dict[str, str]:
    client_slug = output_payload["client"]["client_id"]
    return DeliveryArtifactGenerator().write(output_dir, client_slug, delivery_artifact)


def _resolve_path(base_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    nested = (base_path / path)
    if nested.exists():
        return nested.resolve()
    return path.resolve()


def _resolve_invoice_date(raw_work_log: dict[str, Any]) -> str:
    period = raw_work_log.get("period", {})
    if period.get("end_date"):
        return str(period["end_date"])
    work_items = raw_work_log.get("work_items", [])
    performed_dates = sorted(
        item["performed_on"]
        for item in work_items
        if item.get("performed_on")
    )
    if performed_dates:
        return performed_dates[-1]
    return date.today().isoformat()


if __name__ == "__main__":
    main()
