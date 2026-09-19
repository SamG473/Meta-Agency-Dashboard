# Meta Agency Dashboard

Every client's Meta ad account in one normalised view, each measured against its
own goal. Meta's own Ads Manager makes you switch accounts to answer "how is
everything doing?"; this answers it on one screen, and keeps the daily history
Meta's reporting rolls off.

Built for my own freelance Meta ads work. **The deployed instance runs seeded
demo data — invented agencies, invented figures. The real instance runs locally,
against the Meta API and my own Postgres store.**

## What it does

- **Overview** — portfolio spend, CPM and how many clients are on pace, a daily
  spend chart on a real time axis, and one row per client showing its own goal,
  target, actual and pace state.
- **Analytics** — one client at a time: period-over-period comparison, CPA or
  cost per 1,000 reached (whichever its objective makes meaningful), CTR and
  frequency trends, and a campaign / ad set breakdown.
- **Goal-aware results** — a result is whatever the ad set optimises for: link
  clicks, leads, pixel purchases, or people reached. Summing every action type
  together, as the first version did, roughly doubled the count.

## Architecture

Pull-and-store, never live-query. A nightly GitHub Actions job pulls each
account's insights into Postgres; the dashboard reads only from Postgres, so
rate limits never touch the UI and history survives. Read-only against Meta:
nothing here can pause or edit a campaign.

```
ingest/    Meta pull: campaigns, account and ad set insights
app/       FastAPI, goal-metric registry, pace evaluation
frontend/  React + Vite + Recharts
```

## Running it

```bash
# API (reads DATABASE_URL, falls back to local SQLite)
python -m uvicorn app.main:app --reload

# Dashboard
npm --prefix frontend install
npm --prefix frontend run dev

# Ingest: yesterday by default, or a backfill
python -m ingest.run
python -m ingest.run --since 2026-07-01 --until 2026-07-31
```

`.env` holds `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_IDS` and `DATABASE_URL`, and
is not committed.

## Demo mode

```bash
DEMO_MODE=true python -m uvicorn app.main:app
```

The API then serves a generated fictional portfolio from an in-memory database
and never opens the real one — `DATABASE_URL` is not read at all. The data is
built from a fixed seed, so it looks the same on every load, and the header
carries a standing "Demo data" notice. See `app/demo.py`.
