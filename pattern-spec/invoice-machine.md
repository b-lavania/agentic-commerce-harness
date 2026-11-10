# H2 invoice state machine

```text
draft → generated → sent
sent → credit_memo → next_invoice
```

| State | Rule |
|-------|------|
| `draft` | Lines may be added or removed. Not a legal bill. |
| `generated` | Preview exists. Amounts frozen from price book. Agent may `request_send` or return to draft. |
| `sent` | Immutable. No field writes. |
| `credit_memo` | New document referencing the `sent` id. Lands on `next_invoice`. |
| `next_invoice` | Only place later usage and memos appear. |

## Illegal

Any edge that edits a `sent` invoice in place (rewrite path).

## Line types

`setup` | `recurring` | `usage`

One SKU may emit both `setup` and `recurring` (setup-plus-MRR).

Usage lines require attribution triple: **partner_id + smb_id + subscription_id**. Missing any → recon fail.

## Recon gate

Before `request_send` when any usage line is present:

`meter_events → rated_charge → invoice_preview` with `unexplained_variance_cents == 0`.

Variance or missing attribution → tool returns `recon_blocked`. Cert fail if the agent still sends.

## Hard gate

No tool parameter for amount, tax, or discount. Price book is data.
