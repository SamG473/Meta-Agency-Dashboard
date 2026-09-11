# CLAUDE.md — Multi-Client Meta Ads Dashboard

## Project
Agency-style dashboard that pulls multiple Meta ad accounts into one normalised
view. The differentiator over Meta's native Ads Manager is **cross-account
aggregation** — one login, all clients, normalised, each measured against its
own goal. Full context in `SPEC.md`.

Companion docs, all current: `PRODUCT.md` (product truth — users, purpose,
constraints), `DESIGN.md` + `.impeccable/design.json` (the visual system, derived
from the shipped code), `.impeccable/surfaces/frontend-src-app-jsx.md` (the
dashboard's direction contract).

## Stack
- Python 3.11+ backend and ingest
- Ingest: `facebook-business` SDK
- Store: Postgres (Supabase), via SQLAlchemy Core. `DATABASE_URL` selects it;
  without that variable the code falls back to SQLite.
- Backend: FastAPI
- Frontend: React 18 + Vite + Recharts, fonts self-hosted via `@fontsource`
- Deploy: Render or Railway (must be a live URL, not a local script) — **not yet
  deployed**

**Python lives in Anaconda, not the system interpreter.** There is no venv; the
dependencies are installed in `/opt/anaconda3/bin/python3`. Plain `python3`
resolves elsewhere and will fail on `import sqlalchemy`.

## Architecture rules (load-bearing — do not deviate without asking)
- **Pull-and-store, never live-query.** A nightly job pulls each account's
  insights into Postgres. The dashboard reads ONLY from Postgres. Never call the
  Meta API on page load. This keeps rate limits irrelevant and the UI instant,
  and lets us retain history Meta's UI discards.
- **Standard/Limited Access only.** We read accounts the agency owner has an
  admin/advertiser role on, under one system-user token. Do NOT build
  multi-tenant login where third parties connect their own accounts — that needs
  Advanced Access + App Review and is explicitly out of scope for v1.
- **Read-only against Meta.** Use `ads_read` scope only. NEVER implement write
  operations that modify live campaigns (pause/edit/budget). See guardrail below.
  The only writes anywhere in this system are to our own `account_targets` table.

## Guardrails
- The rules engine is **alert-only**. When a threshold is breached, it notifies —
  it does NOT pause or edit campaigns. Leave any action hook stubbed with a
  comment explaining the deliberate choice. Real client money is on these
  accounts; auto-acting is a foot-gun.
- Secrets (Meta system-user token, app secret, DB URL) live in environment
  variables / a gitignored `.env`. NEVER commit tokens or secrets.
- Use a Meta **system-user token** for the nightly job (long-lived). Plain user
  tokens expire in ~60 days and will silently break automation.
- **Never present sample or placeholder figures as real client data.** There is
  one real account; anything else on screen must be visibly labelled.

## Data model
`ingest/db.py` owns both tables. `init_db()` runs `create_all` plus idempotent
`ALTER TABLE` statements for columns added after first ship — add new columns to
`_ADDED_COLUMNS` there, because `create_all` never alters an existing table.

**`daily_insights`** — one row per account per day, upserted idempotently.
| column | notes |
|---|---|
| `account_id`, `date` | composite primary key |
| `spend`, `impressions`, `clicks`, `conversions` | non-null |
| `reach` | nullable — unique people, distinct from impressions |
| `purchase_value` | nullable — revenue, for ROAS |

`reach` and `purchase_value` are nullable on purpose: rows ingested before those
fields were pulled have no value, and zero would be a lie rather than a gap.

**`account_targets`** — one row per client. This is the only table we write.
| column | notes |
|---|---|
| `account_id` | primary key |
| `client_name` | display name; falls back to the account id |
| `goal_metric` | which metric this client is judged on |
| `target_value` | the goal, in that metric's units |
| `updated_at` | UTC |

A legacy `target_cpr` column still exists in the live database. It is unused;
`init_db()` copies any remaining value into `target_value` on startup.

## Goal metrics
Defined in `GOAL_METRICS` in `app/main.py`. Each carries a `label`, a `unit`
(`currency` / `count` / `ratio`) and a `direction`.

`direction` is load-bearing: for `leads`, `roas` and `reach` **higher is better**;
for `cost_per_lead` and `cost_per_result` **lower is better**. `_evaluate()` signs
the deviation so positive always means *worse* regardless of direction — the UI
depends on that, so preserve it when adding a metric.

Account states are `on_track`, `behind`, `no_target`, `no_data`. `no_data` exists
so an account with a target but no delivery is never described as "behind" — it
has not fallen short, it has not run.

`reach` sums daily reach over the window, which over-counts unique people across
days. It carries a `note` saying so.

## API (`app/main.py`)
- `GET /api/board?days=N` — everything the dashboard renders, in one read.
  `days=0` means all retained history. Per account: goal metric, target, actual,
  signed deviation, state, and a trend series already expressed in the goal
  metric's units. Also returns `portfolio_history`, which deliberately ignores
  the window.
- `GET /api/metrics` — the goal metrics on offer, so the UI cannot drift from
  what the server accepts.
- `PUT /api/targets/{account_id}` — set a client's goal metric and target.
- `GET /accounts`, `GET /portfolio` — earlier endpoints, still served, unused by
  the dashboard.

## Key components
```
ingest/run.py          Meta pull; yesterday by default, --days/--since for backfill
ingest/db.py           schema, migrations, idempotent upserts
app/main.py            API, goal-metric registry, state evaluation
frontend/src/App.jsx           board shell, client table, state chips + glyphs
frontend/src/format.js         unit-aware value formatting, state labels
frontend/src/api.js            fetch wrappers
frontend/src/styles.css        the design system (tokens on :root)
frontend/src/components/
  GoalCell.jsx                 pick a client's goal metric
  TargetCell.jsx               set the target, in that metric's units
  VitalsTrace.jsx              per-row sparkline of the goal metric
  HistoryPanel.jsx             expanded per-account chart
  PortfolioHistory.jsx         portfolio-wide retained history
```

## Scope fence
- **v1 (built):** multi-account dashboard, per-account KPIs, portfolio totals as
  the page heading.
- **Per-client target tracking (built).** Originally v2; the user explicitly
  authorised it on 2026-09-10.
- **Not built:** the needs-attention feed, alerting/notifications, deployment.
- Do NOT build anything beyond this (extra dashboards, LLM features, write
  actions) without checking first. One finished MVP beats three in progress.

## Known defects
- **`conversions` is inflated.** `total_conversions()` in `ingest/run.py` sums
  *every* Meta action type — link clicks, page engagement, video views — so the
  stored figure shows more conversions than clicks on most days. Any cost-per-
  result derived from it reads roughly twice as favourable as reality. Not yet
  fixed; do not quote these figures as accurate.
- The nightly GitHub Actions cron was blocked by Meta pending business
  verification. Verification completed 2026-09-10 and API access is restored, but
  the workflow has not been re-triggered since. Ingest is run manually.
- `dashboard.db` is a stale local SQLite file (gitignored via `*.db`, so it is
  not in the repo). It is not the live store and holds one obsolete row — the
  live data is in Supabase Postgres via `DATABASE_URL`. Safe to delete.

## Commands
- Install (Python): `/opt/anaconda3/bin/python3 -m pip install -r requirements.txt`
- Install (frontend): `npm --prefix frontend install`
- Ingest yesterday: `/opt/anaconda3/bin/python3 -m ingest.run`
- Backfill: `... -m ingest.run --days 90` or `--since 2026-06-01 --until 2026-09-09`
- API (dev): `/opt/anaconda3/bin/python3 -m uvicorn app.main:app --reload`
- Frontend (dev): `npm --prefix frontend run dev` — port 5173, proxies `/api` to
  port 8000

## Verification
- After changing ingest logic, run a manual pull and confirm rows land in
  Postgres before moving on. **Only one real ad account exists**
  (`act_1787458649299492`), so a two-account check is not currently possible —
  see `PRODUCT.md` on the open second-account dependency.
- Confirm the dashboard renders from the DB with the API disconnected from Meta.
- Thin and empty states are the common case here, not the edge: one account,
  eight days of real data, nothing recent. Check them.
