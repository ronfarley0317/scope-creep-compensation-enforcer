# Scope Creep Report: BrightPath Creative

## Executive Summary
The demo workflow identified 3 scope-creep event(s) for BrightPath Creative. Based on the configured contract rules, the current estimated billable impact is USD 1000.00.
Overall, this reflects a 71.4% over-delivery against the agreed scope tracked in this reporting period.
- This represents a 100.0% over-delivery on revision work (4 delivered versus 2 agreed).
- This represents a 100.0% over-delivery on landing page work (2 delivered versus 1 agreed).
- This represents a 50.0% over-delivery on ad creative work (6 delivered versus 4 agreed).

## Scope-Creep Events Detected
### Event 1
- Event ID: `creep-demo-client-demo-work-001`
- Summary: The project included 4 creative for ad creatives. Work delivered exceeded that amount by 2 creative, for a total of 6 creative. This results in an additional charge of USD 400.00.
- Agreed scope amount: 4.0
- Delivered amount: 6.0
- Additional amount beyond scope: 2.0
- Source reference: `task` / `demo-work-001`
- Source excerpt: Delivered six final ad creatives for the April paid social launch.

### Event 2
- Event ID: `creep-demo-client-demo-work-002`
- Summary: The project included 2 rounds for ad creatives. Work delivered exceeded that amount by 2 rounds, for a total of 4 rounds. This results in an additional charge of USD 300.00.
- Agreed scope amount: 2.0
- Delivered amount: 4.0
- Additional amount beyond scope: 2.0
- Source reference: `task` / `demo-work-002`
- Source excerpt: Completed four revision rounds across campaign assets.

### Event 3
- Event ID: `creep-demo-client-demo-work-003`
- Summary: The project included 1 section for landing page. Work delivered exceeded that amount by 1 section, for a total of 2 section. This results in an additional charge of USD 300.00.
- Agreed scope amount: 1.0
- Delivered amount: 2.0
- Additional amount beyond scope: 1.0
- Source reference: `task` / `demo-work-003`
- Source excerpt: Added one extra landing page section requested by the client.

## Revenue Impact
- Estimated total revenue impact: USD 1000.00
- Pricing basis: Sum of config-driven billable event estimates.
- Pricing confidence: high

## Estimated Monthly Revenue Leakage
Based on current activity patterns, projected monthly leakage is approximately USD 1013.83.
- Methodology: Calculated from 3 scope-creep event(s) across 30 days using a weekly leakage rate of USD 233.33, extrapolated over 4.345 weeks.
- Confidence level: high

## Recovery Opportunity
If similar patterns persist, implementing automated enforcement could recover USD 861.76-USD 1013.83 per month.
- Recovery basis: Recovery range applies a 85%-100% capture band based on high confidence in the observed pattern.

## Enforcement Impact
- Without Enforcement:
Additional work completed without compensation
- With Enforcement:
USD 1000.00 captured and billed
- Net Impact:
+ USD 1000.00 recovered revenue

## Recommended Compensation Actions
- Compensation type: `invoice_line_item`
- Client-facing recommendation: These items are recommended for inclusion in the upcoming invoice.
- Draft invoice item `invoice_item_1`: 2 creative x 200 = USD 400.00
- Draft invoice item `invoice_item_2`: 2 rounds x 150 = USD 300.00
- Draft invoice item `invoice_item_3`: 1 section x 300 = USD 300.00

## Assumptions and Notes
- Revision counting is tracked separately from net-new deliverables.
- Landing page sections beyond the base page are tracked as incremental sections.
- Billing is triggered only when work exceeds the included quantity or revision cap.
- This report is generated from normalized SOW and work-log inputs using deterministic contract rules.
- The audit trace below maps each compensation recommendation to a specific normalized event.

## Audit Trace Table
| Event ID | Category | Allowance | Actual | Exceeded | Source | Source Excerpt | Billing Rule | Revenue Calculation |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `creep-demo-client-demo-work-001` | `ad_creative` | 4.0 | 6.0 | 2.0 | `task` / `demo-work-001` | Delivered six final ad creatives for the April paid social launch. | `extra-ad-creatives` | `2 x 200 per creative = 400` |
| `creep-demo-client-demo-work-002` | `revision` | 2.0 | 4.0 | 2.0 | `task` / `demo-work-002` | Completed four revision rounds across campaign assets. | `extra-revisions` | `2 x 150 per rounds = 300` |
| `creep-demo-client-demo-work-003` | `landing_page` | 1.0 | 2.0 | 1.0 | `task` / `demo-work-003` | Added one extra landing page section requested by the client. | `extra-landing-page-sections` | `1 x 300 per section = 300` |
