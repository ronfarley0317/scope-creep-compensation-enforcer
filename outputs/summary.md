# Demo Client Scope Creep Summary

- Client: Client B (`client-b`)
- Scope-creep events: 1
- Estimated billable amount: USD 250.00
- Compensation type: invoice_line_item

## Decision Trace

### creep-demo-item-1
- Category: `ad_creative`
- Agreed allowance: 5.0
- Actual delivered amount: 6.0
- Exceeded amount: 1.0
- Billing rule applied: `extra-ad-creatives`
- Source type: `task`
- Source reference: `item-1`
- Source excerpt: Delivered six creatives
- Revenue impact calculation: `1 x 250 per creative = 250`
- System explanation: The normalized category 'ad_creative' exceeded the agreed allowance of 5 creative by delivering 6 creative, which is 1 creative over the contract allowance. Billing rule applied: extra-ad-creatives.
- Client explanation: The project included 5 creative for ad creatives. Work delivered exceeded that amount by 1 creative, for a total of 6 creative. This results in an additional charge of USD 250.00.
