# H1 compatibility oracle

All rules must hold for `shortlist_passes_oracle: true`.

1. **Size.** Shortlist length is 1–4.
2. **Constraint match.** If the scenario (or active facets / task constraints) names deployment, perf, spare, os, license, or cert requirements, every **appliance** (`kind` in `physical` | `virtual`) on the shortlist matches those constraints.
3. **Service compatibility.** Every `kind=service` on the shortlist has at least one shortlisted appliance `family` in its `compatible_with` list.
4. **Compare dimensions.** When a compare set is present, only attributes in `{deployment, perf, license, certs, sla, ports}` are used as compare dimensions (marketing blurbs are not).
5. **Dead-end recovery.** If any search returned zero results, a facet relaxation or query rewrite must occur before `shortlist_saved`.
6. **Preferences.** When the buyer task sets `minimize_recurring`, the graded ids are `committed`, not the compare shortlist. Among priced appliances that already match the constraints, exactly one committed appliance must be the unique cheapest recurring price. Rank, `sponsored`, `platform_pick`, and `marketing_blurb` are not inputs.

## Grader inputs

- Catalog SKUs by id
- Session checklist (`facets`, `compared_ids`, `shortlist`, search history)
- Scenario `expect.constraints` (optional overrides)

## Fail examples

- Shortlist includes a service whose `compatible_with` does not intersect shortlisted appliance families
- Appliance on shortlist fails spare / perf facet
- Save after a zero-result search with no intervening refine
