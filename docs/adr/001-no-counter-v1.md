# ADR 001 — No Counter dependency in v1

## Status

Accepted

## Context

The full marketplace-to-money story spans three horizons: discovery (H1), entitlements (H2), and settlement (H3 via [Counter](https://github.com/b-lavania/counter)). Counter already has MCP/ACP checkout, payment invariants, and `scenarios/*.json`.

v1 of **agentic-commerce-harness** must certify discovery and entitlement truth without blocking on Counter staging, Stripe, or ACP headers.

## Decision

1. **No runtime dependency** on Counter (no HTTP client, no MCP SDK, no submodule) in v1 CI.
2. H3 is documented only under `integrations/counter/` plus nullable fields on `pattern-spec/handoff-schema.json` (`checkout_session_id`, `currency`, `counter_scenario_id`).
3. Amounts remain absent from handoff; Counter (later) is the only writer of payment totals.
4. Scenario JSON envelope mirrors Counter’s `id` / `steps` / `expect` shape so a sidecar can sit beside this repo without sharing a package.

## Consequences

- H1→H2 curriculum ships with a frozen handoff schema and stops at `invoice_state: sent`.
- End-to-end marketplace-to-money metrics wait for the Counter sidecar.
- Optional later work: `integrations/counter/` calls staging with handoff ids and maps to Counter acceptance scenarios.

## Later sidecar sketch

```text
Handoff JSON
  → integrations/counter/client (future)
  → Counter staging checkout_sessions
  → agent-harness / scenarios/*.json
```

Until then, this ADR forbids importing Counter code into `src/ach/`.

## Spike

[docs/bridge-spike.md](../bridge-spike.md) compared catalogs. Counter’s seed is a cafe menu. This repo’s catalog is workspace computers. No shared SKU, so the bridge does not continue and ADR 002 is not opened.
