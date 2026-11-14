# Phase 0 — Counter bridge spike

**Decision: pivot.** Cert only. [ADR 001](adr/001-no-counter-v1.md) stays. No ADR 002. No Counter HTTP client in this repo.

Checked 13 Nov 2026 against `/home/bl/Documents/GitHub/counter` (`src/store/seed.ts` and scenario fixtures).

## Catalog and cents

| | Harness | Counter |
|---|---|---|
| What it sells | Workspace computers: laptops, mini PCs, cloud desktops, care, backup | Cafe: drip coffee, latte, breakfast burrito |
| Example ids | `nl-14`, `care-desk` | `drip`, `latte`, `burrito` |
| Example cents | `nl-14` setup 150000, recurring 45000; `care-desk` recurring 12000 | `drip` 300, `latte` 450, `burrito` 900 |
| Shared SKUs | none | none |

Office-laptop commitment on the harness ledger, after preview: setup $1,500 + laptop recurring $450 + desk care $120 = **$2,070**. That total is not a Counter ticket. Mapping the three quote lines onto `drip` would be an invented catalog. A shared micro-catalog package is not worth building.

## Demo script (the one we are not filming)

Actors: `BuyerOrg` runs the cert. `CommerceAgent` and `PaymentsAgent` are the two in-process sims. `CounterStore` is a sibling point-of-sale. It does not approve the agent and it does not host the coordinator. That is the BYOA shape: the buyer’s software calls open tools under a written mandate.

1. Commerce: search, facets, compare, attach desk care, save the compare set, **commit** `nl-14` + `care-desk`, `compose_quote`.
2. Handoff: three lines, sku / qty / line type only. `checkout_session_id`, `currency`, and `counter_scenario_id` stay null.
3. Payments: load with bill-to `p-100` / `smb-9` / `sub-77`, attach, preview, send. State `sent`. Ledger shows $2,070. No card capture.
4. Stop. Calling Counter here would open a cafe checkout for a laptop quote.

**Capture vs bill.** `sent` is a legal bill. Capture is a Counter ticket/session with a fake PSP, and only after a real shared catalog exists. Calling Counter after `sent` (stronger) or after quote (faster) both require that catalog. We do not have it.

## One sentence on the ledger

This is a **dual ledger**, said out loud: the harness price book is the B2B bill, and Counter’s seed is a restaurant ticket. They are not two views of one set of cents.

The bill-to triple (`partner_id`, `smb_id`, `subscription_id`) does not map onto a Counter buyer cap. Counter checks ticket totals, comps, and session invariants. The triple is orthogonal.

## Audience

Primary: the B2B cert (quote, mandate, invoice truth) and the portfolio that shows it. The essay frame is bring-your-own-agent: open sim tools, preview before send, the customer’s delegate on the trace, no vendor-hosted coordinator.

The Counter / ACP pitch belongs to Counter. This repo should not grow a second fake merchant to tell it.

## What this repo is, for now

A research sandbox and a portfolio cert. Not a sidecar kit, not a cert SaaS. The sidecar stays parked until a real shared catalog exists. ACES market-share lab, ACP-only checkout, and ERP orchestration stay on the shelf.

Certified catalog is not certified checkout. The handoff is the wall between them: sku, quantity, line type cross; cents, rank, badges, and blurbs do not.
