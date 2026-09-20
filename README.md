Meta Agency Dashboard
Every client's Meta ad account in one normalised view, each measured against its own goal.
<!-- ![Overview page](docs/screenshot.png) --> <!-- Live demo: <url> -->

Why it exists
Built for freelance Meta ads work. Meta Ads Manager displays only one ad account at a time, which makes managing multiple clients slow and fragmented. This dashboard consolidates all client accounts into a single view, with portfolio-wide totals and trend charts that surface underperformance early and support faster, better-informed campaign adjustments.

What it does
Overview shows the portfolio: total spend, number of accounts, CPM, and how many clients are on pace. Underneath, a daily spend chart on a real time axis, and one row per client with its goal, target, actual and pace state.
Analytics takes one client at a time, read-only: period-over-period comparison, CPA or cost per 1,000 reached (whichever the objective makes meaningful), CTR and frequency trends, and a campaign / ad set breakdown.
Architecture
A nightly GitHub Actions job pulls each account's insights into PostgreSQL; the dashboard avoids live quieies to avoid hitting the Meta marketing Api rate limits. 
Python, FastAPI and PostgreSQL (Supabase) on the back end; React + Vite + Recharts on the front.
ingest/    Meta pull: campaigns, account and ad set insights
app/       FastAPI, goal-metric registry, pace evaluation
frontend/  React + Vite + Recharts

Running it
# API (reads DATABASE_URL, falls back to local SQLite)
python -m uvicorn app.main:app --reload

# Dashboard
npm --prefix frontend install
npm --prefix frontend run dev

# Ingest: yesterday by default, or a backfill
python -m ingest.run
python -m ingest.run --since 2026-07-01 --until 2026-07-31
.env holds META_ACCESS_TOKEN, META_AD_ACCOUNT_IDS and DATABASE_URL, and is not committed.

Demo mode
DEMO_MODE=true python -m uvicorn app.main:app
The deployed instance runs in demo mode: a seeded six-client portfolio with mixed objectives. The API serves it from an in-memory database and never opens the real one. The real instance runs locally against the Meta API. See app/demo.py.
