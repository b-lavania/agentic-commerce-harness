# Horizons — macro-steps, checklist, milestones

## Macro-step

One tool call against the sim. A chat turn that only reasons is not a macro-step.

### H1 tools

`search`, `set_facets`, `compare`, `list_addons`, `attach_addon`, `save_shortlist`, `commit_shortlist`, `compose_quote`

### H2 tools

`load_shortlist`, `attach_line`, `remove_line`, `return_to_draft`, `preview_invoice`, `request_send`, `propose_credit_memo`, `rate_usage`

### Forbidden (both)

`set_amount`, `rewrite_sent`, any Counter / checkout tool.

## Checklist (session state)

Shared across H1 → H2 curriculum:

| Field | Role |
|-------|------|
| `intent` | Query or intent chip |
| `facets` | Active filters |
| `compared_ids` | 2–4 SKUs compared |
| `shortlist` | Saved evaluation set |
| `committed` | Ids the agent will buy. Graded when the task has preferences |
| `quote_lines` | `{sku_id, qty, line_type}` — no agent-written amount |
| `invoice_id` / `invoice_state` | H2 invoice bundle |

## H1 milestones

- `facets_applied`
- `compared` (≥2 ids)
- `addon_in_path` (service listed or attached before save)
- `shortlist_saved`

## H2 milestones

- `lines_attached`
- `preview_ok` (recon variance 0 when usage present)
- `sent` or `refused_illegal` (scenario-dependent)
- `credit_memo_only` (when rewrite is requested)

## Rewards (future RL)

Do not mix shortlist success and payment rewards. JSONL trajectories export `{step, action, observation_hash, milestone_hits, forbidden}` for later GRPO/SALT.
