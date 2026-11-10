# Counter sidecar (deferred)

**v1:** documentation only. No runtime dependency on [Counter](https://github.com/b-lavania/counter).

See [docs/adr/001-no-counter-v1.md](../../docs/adr/001-no-counter-v1.md).

## Handoff contract

Frozen schema: [`pattern-spec/handoff-schema.json`](../../pattern-spec/handoff-schema.json).

Required:

- `shortlist_ids`
- `quote_lines[{sku_id, qty, line_type}]`

Nullable H3 stubs (unused in v1):

- `checkout_session_id`
- `currency`
- `counter_scenario_id`

Amounts are never present on the handoff. Counter remains the only writer of payment totals when integrated.

## Future attachment

1. Accept H2 handoff JSON from `ach.driver.curriculum`.
2. Open a Counter staging `checkout_sessions` (or ACP) request using line references — not agent-authored cents.
3. Map failures to Counter scenario ids (e.g. `05_total_mismatch`).
4. Keep this package import-free from Counter until an explicit ADR revises 001.
