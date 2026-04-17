# Demo Client Scope Creep Summary

- Client: BrightPath Creative (`demo-client`)
- Scope-creep events: 3
- Estimated billable amount: USD 1000.00
- Compensation type: invoice_line_item

## Decision Trace

### creep-demo-client-demo-work-001
- Category: `ad_creative`
- Agreed allowance: 4.0
- Actual delivered amount: 6.0
- Exceeded amount: 2.0
- Billing rule applied: `extra-ad-creatives`
- Source type: `task`
- Source reference: `demo-work-001`
- Source excerpt: Delivered six final ad creatives for the April paid social launch.
- Revenue impact calculation: `2 x 200 per creative = 400`
- System explanation: The normalized category 'ad_creative' exceeded the agreed allowance of 4 creative by delivering 6 creative, which is 2 creative over the contract allowance. Billing rule applied: extra-ad-creatives.
- Client explanation: The project included 4 creative for ad creatives. Work delivered exceeded that amount by 2 creative, for a total of 6 creative. This results in an additional charge of USD 400.00.

### creep-demo-client-demo-work-002
- Category: `revision`
- Agreed allowance: 2.0
- Actual delivered amount: 4.0
- Exceeded amount: 2.0
- Billing rule applied: `extra-revisions`
- Source type: `task`
- Source reference: `demo-work-002`
- Source excerpt: Completed four revision rounds across campaign assets.
- Revenue impact calculation: `2 x 150 per rounds = 300`
- System explanation: The normalized category 'revision' exceeded the agreed allowance of 2 rounds by delivering 4 rounds, which is 2 rounds over the contract allowance. Billing rule applied: extra-revisions.
- Client explanation: The project included 2 rounds for ad creatives. Work delivered exceeded that amount by 2 rounds, for a total of 4 rounds. This results in an additional charge of USD 300.00.

### creep-demo-client-demo-work-003
- Category: `landing_page`
- Agreed allowance: 1.0
- Actual delivered amount: 2.0
- Exceeded amount: 1.0
- Billing rule applied: `extra-landing-page-sections`
- Source type: `task`
- Source reference: `demo-work-003`
- Source excerpt: Added one extra landing page section requested by the client.
- Revenue impact calculation: `1 x 300 per section = 300`
- System explanation: The normalized category 'landing_page' exceeded the agreed allowance of 1 section by delivering 2 section, which is 1 section over the contract allowance. Billing rule applied: extra-landing-page-sections.
- Client explanation: The project included 1 section for landing page. Work delivered exceeded that amount by 1 section, for a total of 2 section. This results in an additional charge of USD 300.00.
