# Meta Agency Dashboard

[![Tests](https://github.com/SamG473/Meta-Agency-Dashboard/actions/workflows/tests.yml/badge.svg)](https://github.com/SamG473/Meta-Agency-Dashboard/actions/workflows/tests.yml)

Every client's Meta ad account in one normalised view, each measured against its own goal.

**[Live demo](https://meta-agency-dashboard-web.onrender.com)**. The demo server is hosted on a free tier and suspends when idle. The first request may take up to a minute.

![Overview page](docs/screenshot.png)

Meta Ads Manager displays only one ad account at a time, which makes managing multiple clients slow and fragmented. Built for freelance Meta ads work, this dashboard consolidates all client accounts into a single view, with portfolio-wide totals and trend charts that surface underperformance early and support faster, better-informed campaign adjustments.

The deployed instance runs a seeded six-client portfolio with mixed objectives. No figure on it comes from a real ad account.

## What it does

- **Overview** shows the portfolio: total spend, number of accounts, CPM, and how many clients are on pace. Underneath, a daily spend chart on a real time axis, and one row per client with its goal, target, actual and pace state.
- **Analytics** takes one client at a time, read-only: period-over-period comparison, CPA or cost per 1,000 reached (whichever the objective makes meaningful), CTR and frequency trends, and a campaign / ad set breakdown.

## Quick start (demo mode)

Runs the whole app on the seeded demo portfolio. No database, Meta account or credentials needed.

Requires **Python 3.11+** and **Node.js 18+**.

```bash
git clone https://github.com/SamG473/Meta-Agency-Dashboard.git
cd Meta-Agency-Dashboard

# API, on port 8000
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DEMO_MODE=true python -m uvicorn app.main:app

# Dashboard, in a second terminal, on port 5173
npm --prefix frontend install
npm --prefix frontend run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to the API on port 8000.

## Architecture

```mermaid
flowchart LR
    meta[Meta Marketing API] -->|nightly, read-only| ingest[ingest/run.py<br/>GitHub Actions cron]
    ingest -->|upsert| db[(PostgreSQL<br/>Supabase)]
    db --> api[FastAPI<br/>app/main.py]
    api -->|JSON| ui[React dashboard<br/>frontend/]
```

- **Pull and store, never live-query.** A nightly job pulls each account's insights into PostgreSQL, and the API reads only from there. Page loads never touch Meta, so they are fast however many accounts are connected, the Marketing API's rate limits stay irrelevant, and history Meta's own interface discards is kept.
- **Read-only against Meta.** The ingest uses the `ads_read` scope and never changes a campaign. The only writes the API makes are to its own `account_targets` table, when a client's goal is set.
- **"Results" means the ad set's own objective.** Meta reports every action an ad produced; the ingest counts only the one each ad set optimises for (`ingest/results.py`), so a reach campaign is never given a cost per conversion.
- **Quiet nights are normal.** With nothing delivering, the ingest still succeeds and writes a heartbeat row, so an idle database is never mistaken for an abandoned one. Its logs, public on GitHub, print counts only and mask account ids.

## Tech stack

- Python 3.11+, FastAPI, SQLAlchemy Core: API, goal-metric registry, pace evaluation
- PostgreSQL (Supabase): insights store, with a SQLite fallback for local runs
- React 18, Vite, Recharts, React Router: dashboard
- `facebook-business` SDK: Meta Marketing API
- GitHub Actions: nightly ingest, and tests on every push
- Render: demo deployment (`render.yaml`)

## Running against real data

Copy the template and fill it in:

```bash
cp .env.example .env
```

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | API, ingest | Postgres connection string. Unset falls back to a local SQLite file, `dashboard.db` |
| `META_ACCESS_TOKEN` | ingest | Meta system-user token with `ads_read`. Plain user tokens expire after about 60 days |
| `META_AD_ACCOUNT_IDS` | ingest | Comma-separated ad account ids, e.g. `act_123,act_456` |
| `META_APP_ID`, `META_APP_SECRET` | ingest | Optional; only needed if the Meta app requires an app secret proof |
| `DEMO_MODE` | API | `true` serves the seeded demo portfolio and never opens the real store |
| `FRONTEND_ORIGIN` | API | Deployed dashboard origin(s) allowed through CORS, comma-separated |
| `VITE_API_BASE_URL` | dashboard build | API address when it is on another host; unset uses the dev proxy |

The ingest creates the database tables, so run it before starting the API:

```bash
# Ingest: yesterday by default
python -m ingest.run

#    or a backfill over a date range
python -m ingest.run --since 2026-07-01 --until 2026-07-31

# API, then the dashboard as in the quick start
python -m uvicorn app.main:app --reload
npm --prefix frontend run dev
```

## Running the tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Locally the tests use a throwaway in-memory SQLite database, so they need no setup and never touch the real store or the Meta API. To run them against Postgres instead, as CI does, point `TEST_DATABASE_URL` at a database whose name contains `test` (the suite refuses any other name, because it drops every table when it finishes):

```bash
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/dashboard_test pytest
```

| File | Covers |
| --- | --- |
| `tests/test_metrics.py` | Derived metrics: CTR, cost per result, ROAS, pacing, period-over-period change, including zero-denominator cases |
| `tests/test_results.py` | Which Meta action counts as a "result" for each optimisation goal |
| `tests/test_api.py` | The API endpoints, against a small seeded fake dataset |
| `tests/test_ingest.py` | The nightly ingest with the Meta SDK faked: a no-delivery night, a normal night, an unreachable database |

Python is formatted and linted with [Ruff](https://docs.astral.sh/ruff/):

```bash
ruff format .
ruff check .
```

GitHub Actions runs the lint, format check and tests on every push and pull request, against a Postgres service container (`.github/workflows/tests.yml`).

## Repository layout

| Path | Purpose |
| --- | --- |
| `ingest/` | Meta pull: campaigns, account and ad set insights, result counting, schema |
| `app/` | FastAPI, goal-metric registry, pace evaluation |
| `app/demo.py` | Seeded six-client portfolio for demo mode |
| `frontend/` | React + Vite + Recharts dashboard |
| `tests/` | pytest suite |
| `docs/DESIGN.md` | The dashboard's visual system |
| `.github/workflows/` | Nightly ingest and CI |
| `render.yaml` | Render blueprint for the demo deployment |
| `CLAUDE.md` | Working notes for AI-assisted development: architecture rules and conventions |
