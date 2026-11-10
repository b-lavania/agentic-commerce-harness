# agentic-commerce-harness

Cert harness and in-process sims for commerce agents on **search-first marketplace discovery** (Horizon 1) and **entitlement / invoice truth** (Horizon 2).

Horizon 3 (Counter settlement) is **deferred** — see [`integrations/counter/`](integrations/counter/) and [`docs/adr/001-no-counter-v1.md`](docs/adr/001-no-counter-v1.md).

## Horizons

| Horizon | What it certifies | Terminal success |
|---------|-------------------|------------------|
| **H1 Discovery** | Search → facets → compare → compatible add-ons → shortlist | Shortlist passes compatibility oracle |
| **H2 Entitlements** | SKU attach, typed invoice lines, recon gate | Recon pass; no rewrite of `sent` invoices |
| **H3 Settlement** | Counter MCP/ACP (later sidecar) | N/A in v1 |

Agents never author **amounts**. The sim price book / ledger owns cents.

## Quick start

Prefer the `.sh` / `.bat` pairs under [`scripts/`](scripts/README.md):

```bash
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/test.sh
./scripts/harness.sh
./scripts/curriculum.sh
```

```bat
scripts\install.bat
scripts\test.bat
scripts\harness.bat
scripts\curriculum.bat
```

## Layout

```text
pattern-spec/     # schemas, oracle rules, invoice machine, handoff
horizons/         # catalog seed, scenarios, price book, fixtures
src/ach/          # discovery + entitlements sims, harness, H1→H2 driver
harness/          # thin CLI entry docs
integrations/counter/  # ADR + handoff stub only (no runtime dep)
docs/adr/
```

## Scenario envelope

Same shape as Counter scenarios (`id`, `steps`, `expect`) with commerce actions — no shared package with Counter.

## Evaluation

```bash
./scripts/test.sh
./scripts/harness.sh --jsonl /tmp/ach-trajectories.jsonl
```
