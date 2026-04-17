# Scope Creep Report: Client B

## Executive Summary
The demo workflow identified 1 scope-creep event(s) for Client B. Based on the configured contract rules, the current estimated billable impact is USD 250.00.
Overall, this reflects a 20.0% over-delivery against the agreed scope tracked in this reporting period.
- This represents a 20.0% over-delivery on ad creative work (6 delivered versus 5 agreed).

## Scope-Creep Events Detected
### Event 1
- Event ID: `creep-demo-item-1`
- Summary: The project included 5 creative for ad creatives. Work delivered exceeded that amount by 1 creative, for a total of 6 creative. This results in an additional charge of USD 250.00.
- Agreed scope amount: 5.0
- Delivered amount: 6.0
- Additional amount beyond scope: 1.0
- Source reference: `task` / `item-1`
- Source excerpt: Delivered six creatives

## Revenue Impact
- Estimated total revenue impact: USD 250.00
- Pricing basis: Sum of config-driven billable event estimates.
- Pricing confidence: high

## Estimated Monthly Revenue Leakage
Based on current activity patterns, projected monthly leakage is approximately USD 7500.00.
- Methodology: Calculated from 1 scope-creep event(s) across 1 days using a daily leakage rate of USD 250.00, extrapolated over 30 days.
- Confidence level: low

## Recovery Opportunity
If similar patterns persist, implementing automated enforcement could recover USD 3000.00-USD 5625.00 per month.
- Recovery basis: Recovery range applies a 40%-75% capture band based on low confidence in the observed pattern.

## Enforcement Impact
- Without Enforcement:
Additional work completed without compensation
- With Enforcement:
USD 250.00 captured and billed
- Net Impact:
+ USD 250.00 recovered revenue

## Recommended Compensation Actions
- Compensation type: `invoice_line_item`
- Client-facing recommendation: These items are recommended for inclusion in the upcoming invoice.
- Draft invoice item `invoice_item_1`: 1 creative x 250 = USD 250.00

## Assumptions and Notes
- This report is generated from normalized SOW and work-log inputs using deterministic contract rules.
- The audit trace below maps each compensation recommendation to a specific normalized event.

## Audit Trace Table
| Event ID | Category | Allowance | Actual | Exceeded | Source | Source Excerpt | Billing Rule | Revenue Calculation |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `creep-demo-item-1` | `ad_creative` | 5.0 | 6.0 | 1.0 | `task` / `item-1` | Delivered six creatives | `extra-ad-creatives` | `1 x 250 per creative = 250` |
