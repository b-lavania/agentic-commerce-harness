# H2 invoice state machine

```text
draft → generated → sent
sent → credit_memo → next_invoice
```

| State | Rule |
|-------|------|
| `draft` | Lines may be added or removed. Not a legal bill. |
| `generated` | Preview exists. Amounts frozen from price book. Agent may `request_send` or `return_to_draft`. `attach_line` / `remove_line` here returns “return to draft before editing lines”. |
| `sent` | Immutable. No field writes. |
| `credit_memo` | New document referencing the `sent` id. `line_refs` must exist on that invoice. The ledger copies those cents. The memo accepts no amount. Sent lines stay byte-for-byte. |
| `next_invoice` | Only place later usage and memos appear. |

## Illegal

Any edge that edits a `sent` invoice in place (rewrite path).

## Line types

`setup` | `recurring` | `usage`

One SKU may emit both `setup` and `recurring` (setup-plus-MRR).

Usage lines require attribution triple: **partner_id + smb_id + subscription_id**. Missing any → recon fail.

## Recon gate

`rate_usage` stores a rated batch and does not attach a line. The agent then `attach_line`s `usage` with the same units and the same attribution triple. Preview requires usage-line cents to equal rated-batch cents.

Before `request_send`:

- state is `generated` (preview already happened)
- `unexplained_variance_cents == 0`
- if bill-to was set, the partner / smb / subscription triple is complete

`meter_events → rated_charge → invoice_preview` with `unexplained_variance_cents == 0`.

Variance or missing attribution → tool returns `recon_blocked`. Cert fail if the agent still sends.

## Hard gate

No tool parameter for amount, tax, or discount. Price book is data.
