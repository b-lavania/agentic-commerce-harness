# Docs site

Static landing for this repo. No build step and no server.

## Open locally

```bash
# from repo root
xdg-open docs/index.html   # Linux
# open docs/index.html     # macOS
# start docs/index.html    # Windows
```

Or open [`index.html`](index.html) from a file browser.

## Pages

| File | Role |
|------|------|
| [`index.html`](index.html) | Landing page (CapEcon chrome) |
| [`insights.md`](insights.md) | Long-form claims with Shipped / Planned / Out of scope |
| [`roadmap.md`](roadmap.md) | Badge legend and cert order |
| [`adr/001-no-counter-v1.md`](adr/001-no-counter-v1.md) | No Counter dependency in v1 |

## GitHub Pages

1. Repo **Settings → Pages**.
2. Source: **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`.
4. Save. The site will be at `https://<owner>.github.io/<repo>/` once published.

Assets live under [`assets/`](assets/) (`style.css`, `handoff.svg`). Pattern-spec links on the landing page point at the GitHub `blob/main/pattern-spec/…` URLs so they work when Pages serves only `/docs`.
