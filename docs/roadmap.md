# Roadmap

Badge legend used on the [landing page](index.html) and in [insights.md](insights.md).

| Badge | Meaning |
|-------|---------|
| **Shipped** | In the tree at v0.1 (`0.1.0`, six scenarios, pytest). |
| **Planned** | Agreed in the cert design, not in the tree yet. |
| **Out of scope** | Stated so the page does not imply them. |

## Shipped (v0.1)

- H1 discovery sim and compatibility oracle
- H2 entitlement / invoice sim
- Six gold scenarios under `horizons/*/scenarios/`
- Curriculum driver H1 → H2 stopping at `invoice_state: sent`
- JSONL trajectory export
- Handoff schema with nullable Counter stubs
- [ADR 001](adr/001-no-counter-v1.md) — no Counter runtime dependency

## Planned (cert order)

1. Grading seam and a real incompatible-addon refusal
2. Quote terminal (`commit_shortlist`, `compose_quote`) and curriculum fail-closed on missing price-book lines
3. Payments machine: `return_to_draft`, split `rate_usage` from attach, memo line refs
4. Buyer task with preference, position decoy, listing overlays, and mandate caps
5. Trace page (`--view`) with commerce / handoff / payments lanes
6. Counter sidecar only after a new ADR revises 001

## Out of scope

- Live checkout demo or Counter HTTP in CI
- Model leaderboard or market-share tables
- Seller-agent listing rewrite loop
- Visual product shelf, star ratings, review counts
- OAuth agent credentials / consent APIs
- Loyalty, delivery address, substitution rules
- Internal employee / warehouse / SaaS-embedded agents
- Reward training / RL mixer
