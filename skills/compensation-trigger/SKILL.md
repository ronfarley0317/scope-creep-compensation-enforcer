---
name: compensation-trigger
description: Generate compensation artifacts from validated scope-creep events. Use when a scope-creep event has already been identified and the goal is to create a compensation action such as an invoice line item, change order, or approval request. Do not use it to decide whether scope creep exists.
---

# Compensation Trigger

Generate compensation artifacts from validated scope-creep events and return structured JSON plus a human-readable draft.

## Workflow

1. Read the validated scope-creep events first.
2. Read any available billing rules, pricing basis, client context, and work references second.
3. Choose the narrowest compensation action supported by the available data.
4. Produce structured draft artifacts with traceable references.
5. Produce a short human-readable draft that can be used internally or adapted for the client.

## Decision Rules

- Do not re-litigate whether scope creep exists. Treat the incoming creep events as validated input.
- Prefer `invoice_line_item` when pricing is explicit and approval is not required before billing.
- Prefer `change_order` when work changes contracted scope, requires formal approval, or pricing needs approval before invoicing.
- Prefer `approval_request` when the event is billable in principle but rate, quantity, or authorization is missing.
- If multiple events require different actions, choose `mixed`.
- Do not invent pricing. If the amount is unknown, keep monetary fields `null` and make the approval dependency explicit.

## Artifact Selection Heuristics

Use these defaults unless the source data states otherwise:

- `invoice_line_item`
  Use when the contract or billing rules already define rate, unit, and chargeability.
- `change_order`
  Use when the work represents net-new scope, substantial scope expansion, or requires client signoff.
- `approval_request`
  Use when internal or client approval is required before billing or before continuing the work.
- `mixed`
  Use when the events do not fit one single artifact type.

## Field Guidance

### `compensation_type`

Return one of:

- `invoice_line_item`
- `change_order`
- `approval_request`
- `mixed`

### `draft_invoice_line_items`

Return one object per billable draft line item.

Include when available:

- `line_item_id`
- `event_id`
- `description`
- `quantity`
- `unit`
- `rate`
- `currency`
- `amount`
- `status`

Return an empty array when invoice drafting is not yet supported by the available data.

### `draft_change_order_summary`

Return one object summarizing the draft change order.

Include when available:

- `title`
- `scope_change_summary`
- `related_event_ids`
- `pricing_summary`
- `schedule_impact`
- `approval_required`

Use `null` when a change order is not the right artifact.

### `internal_approval_note`

Return one object for internal reviewers.

Include when available:

- `summary`
- `recommended_action`
- `risks`
- `missing_information`

### `client_facing_summary`

Return one object suitable for adapting into external communication.

Keep it factual, short, and non-accusatory.

Include when available:

- `summary`
- `requested_action`
- `pricing_statement`
- `timeline_statement`

## Human-Readable Draft

After the structured JSON, provide a short human-readable draft with these sections:

- `Internal Draft`
- `Client Draft`

Keep both concise and directly grounded in the structured output.

## Output Contract

Return the response in two parts:

1. A JSON object with the required keys
2. A human-readable draft immediately after the JSON

Use this JSON shape:

```json
{
  "compensation_type": "invoice_line_item",
  "draft_invoice_line_items": [
    {
      "line_item_id": "line_1",
      "event_id": "creep_2",
      "description": "Out-of-scope CRM migration support",
      "quantity": 4,
      "unit": "hours",
      "rate": 150,
      "currency": "USD",
      "amount": 600,
      "status": "draft"
    }
  ],
  "draft_change_order_summary": null,
  "internal_approval_note": {
    "summary": "Validated scope-creep event is billable under the contract's out-of-scope hourly rule.",
    "recommended_action": "Approve draft invoice line item for next billing cycle.",
    "risks": [
      "Confirm whether the client requested pre-approval for CRM-related work."
    ],
    "missing_information": []
  },
  "client_facing_summary": {
    "summary": "We completed work outside the originally agreed scope related to CRM migration support.",
    "requested_action": "Please confirm approval to include this item in billing.",
    "pricing_statement": "This work is billed at the agreed out-of-scope rate of 150 USD/hour for 4 hours, totaling 600 USD.",
    "timeline_statement": "No schedule change is currently required."
  }
}
```

Use this draft format after the JSON:

```text
Internal Draft
Recommend billing validated out-of-scope CRM migration support as one draft invoice line item for 4 hours at 150 USD/hour, totaling 600 USD. No schedule change identified. Confirm whether any pre-approval requirement applies before finalizing billing.

Client Draft
We identified work completed outside the original scope related to CRM migration support. Under the agreed out-of-scope billing terms, this work totals 600 USD. Please confirm approval for inclusion on the upcoming invoice.
```

## Response Requirements

- Return the JSON first.
- Return the human-readable draft second.
- Do not add analysis outside those two parts.
- Do not include keys outside the required output unless the user explicitly asks for them.
- Keep billing language factual and audit-friendly.
