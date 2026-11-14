# Roadmap

Badge legend used on the [landing page](index.html) and in [insights.md](insights.md).

| Badge | Meaning |
|-------|---------|
| **Shipped** | In the tree (`0.1.0`, fifteen scenarios, pytest). |
| **Planned** | Agreed and not in the tree yet. |
| **Out of scope** | Stated so the page does not imply them. |

## Shipped

- H1 discovery sim, quote (`commit_shortlist`, `compose_quote`), and compatibility oracle including `minimize_recurring` on the commit
- H2 invoice sim: bill-to, `return_to_draft`, `remove_line`, rate-then-attach, memo `line_refs`
- Fifteen gold scenarios under `horizons/*/scenarios/`
- `ScriptedPolicy` plus per-step `expect`
- Curriculum driver H1 → H2 stopping at `invoice_state: sent`, fail-closed on an unpriced SKU
- JSONL trajectory export and `--view` three-lane replay
- Handoff schema with nullable Counter stubs
- [ADR 001](adr/001-no-counter-v1.md) and the [pivot note](bridge-spike.md)

## Planned

1. Zero-result recovery scenario and a blurb-bait scenario (loudest seller text loses)
2. A model client behind `ScriptedPolicy` — same observation, same grader
3. Counter sidecar only if a shared catalog exists. The spike said it does not. No ADR 002 until that changes.

## Out of scope

- Live checkout demo or Counter HTTP in CI
- Model leaderboard or market-share tables
- Seller-agent listing rewrite loop
- Visual product shelf, star ratings, review counts
- OAuth agent credentials / consent APIs
- Loyalty, delivery address, substitution rules
- Internal employee / warehouse / SaaS-embedded agents
- Reward training / RL mixer
