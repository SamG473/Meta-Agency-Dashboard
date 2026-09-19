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
- Frontend: React 18 + Vite + Recharts + React Router 7 (`BrowserRouter`), fonts
  self-hosted via `@fontsource`. Routes use real paths, so a static host must
  rewrite unknown paths to `index.html` or a direct `/analytics` link will 404.
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
| `frequency` | nullable — impressions per person that day, as Meta calculated it. Pulled, never derived: it is impressions ÷ reach for the period asked for, and reach does not add up across days, so a week's frequency is not the mean of its days. Null wherever `reach` is null |
| `results` | nullable — each ad set's own optimisation outcome, summed for the day |
| `results_basis` | nullable — `action`, `reach`, `mixed` or `unmapped` |

`conversions` is the legacy sum of every Meta action type. It is still written,
so history stays intact, but nothing in the app reads it: `results` replaced it
on 2026-09-13.

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

**`adset_daily_insights`** — one row per ad set per day, upserted idempotently by
the same ingest run. Feeds the Analytics breakdown; campaign totals are a
grouping of these rows.
| column | notes |
|---|---|
| `account_id`, `adset_id`, `date` | composite primary key |
| `adset_name`, `campaign_id`, `campaign_name` | kept per day; the API shows the latest names |
| `spend`, `impressions`, `clicks`, `conversions` | non-null; `conversions` is the legacy all-actions sum |
| `reach`, `optimization_goal`, `result_action_type`, `results`, `cost_per_result` | nullable — what this ad set optimises for, what that outcome is, and what Meta says it cost |

**`campaigns`** — each campaign's current state, refreshed on every run. A
snapshot, not a time series: it answers "what is live right now", which is what
`portfolio.active_campaigns` reports.
| column | notes |
|---|---|
| `account_id`, `campaign_id` | composite primary key |
| `name` | campaign name |
| `effective_status` | Meta's rollup, which already accounts for pauses above the campaign |
| `account_active` | false when the ad account itself is not active (`account_status` ≠ 1) |
| `updated_at` | UTC |

Campaigns Meta stops returning are deleted from this table on the next run, so a
vanished campaign cannot go on being counted as active.

## Goal metrics
Defined in `GOAL_METRICS` in `app/main.py`. Each carries a `label`, a `unit`
(`currency` / `count` / `ratio`) and a `direction`.

`direction` is load-bearing: for `leads`, `roas` and `reach` **higher is better**;
for `cost_per_lead` and `cost_per_result` **lower is better**. `_evaluate_rate()`
signs the deviation so positive always means *worse* regardless of direction.

`cumulative` is the other load-bearing flag. `leads` and `reach` accumulate over
a period, so their targets are **paced**: 24,000 reach is 40% delivered at 40%
elapsed. Rate metrics (`cost_per_result`, `cost_per_lead`, `roas`) cannot be
paced — a £2 cost per lead is not £0.80 at 40% elapsed — so they are compared
with their target directly, and carry no `pace` block.

## Goal periods and state (`app/main.py`)
A cumulative goal is judged against **pace**, never against the full target: a
figure under the total means nothing without knowing how much of the period is
left. The period comes, in order: a `period_start`/`period_end` set by hand on
`account_targets`; otherwise the ACTIVE campaigns running today; otherwise the
most recently finished campaign, so a goal can still read met or missed. A
campaign with no `stop_time` is open-ended and cannot be paced.

`elapsed_fraction = elapsed_days / total_days` (whole days, clamped 0–1),
`expected_to_date = target × elapsed_fraction`, `pace_ratio = actual ÷ expected`.
The actual used is the **period's own**, not the selected 30/90/All window, so
changing the window never changes a badge. The at-risk floor lives in one place:
`AT_RISK_PACE`.

Account states:
| state | meaning |
|---|---|
| `on_track` | `pace_ratio >= 1.0`, or a rate goal meeting its target |
| `at_risk` | `AT_RISK_PACE <= pace_ratio < 1.0` |
| `behind` | `pace_ratio < AT_RISK_PACE`, or a rate goal missing its target |
| `met` / `missed` | period ended, actual at or above / below target |
| `not_started` | period begins in the future |
| `no_end_date` | cumulative target with no period end. **Never** fall back to comparing against the full target here — that is the misleading behaviour this replaced |
| `no_target`, `no_data` | no goal set; or a goal with no delivery — it has not fallen short, it has not run |

`reach` sums daily reach over the window, which over-counts unique people across
days. It carries a `note` saying so. Analytics' cost per 1,000 reached divides by
that same summed reach, so the window figure reads slightly cheap for the same
reason; the per-day points on its chart are pulled per day and are exact.

For an account whose ad sets optimise for reach (`results_basis` of `reach`, or
`unmapped`), `cost_per_result`, `cost_per_lead` and `leads` return None rather
than a mislabelled figure: there is no conversion to price. Analytics prices
those clients per 1,000 people reached instead, and never calls it CPA.

## API (`app/main.py`)
- `GET /api/board?days=N` — everything the dashboard renders, in one read.
  `days=0` means all retained history. Per account: goal metric, target, actual,
  signed deviation, state, and a trend series already expressed in the goal
  metric's units. `portfolio_history` is scoped to the same window as the tiles,
  so the whole Portfolio totals panel describes one range. `retention`
  (`days_stored`, `first_date`, `last_date`, `starts_after_window`) reports what
  the store holds, separately — a window reaching back further than the record
  says so rather than silently showing a different range.
  `portfolio.active_campaigns` is live campaign state and cannot be windowed,
  because status is only ever current. The board stopped displaying it on
  2026-09-18 — the row shows Spend, Accounts, CPM and On pace — but the figure
  and its rule stay, ready to return. It is None, never 0, when no campaign has
  ever been synced. It counts campaigns
  `_is_delivering()` accepts — ACTIVE is not enough on its own, since a campaign
  whose flight ended still reports ACTIVE forever unless somebody paused it.
  `portfolio.cpm` is spend ÷ impressions × 1000 over the window (impressions,
  not reach: they add up across days and exist whatever the objective).
  `on_pace` / `pace_judged` / `pace_excluded` count clients meeting their pace
  out of those whose pace can be judged at all.
- `GET /api/metrics` — the goal metrics on offer, so the UI cannot drift from
  what the server accepts.
- `PUT /api/targets/{account_id}` — set a client's goal metric and target.
- `GET /api/analytics?account_id=…&days=N` — one client, read-only: totals for the
  window and for the equal-length period before it (none when `days=0`), signed
  changes, daily CPA / cost-per-1,000-reached / CTR / frequency series, and the
  ad set breakdown. Cost is split by goal: `has_conversion_spend` and
  `has_awareness_spend` say which cost stats mean anything. Omitting
  `account_id` picks the first known account.

## Key components
```
ingest/run.py          Meta pull: campaign state, then account + ad set
                       insights; yesterday by default, --days/--since to backfill
ingest/db.py           schema, migrations, idempotent upserts
ingest/results.py      optimisation goal → what counts as a result
app/main.py            API, goal-metric registry, state evaluation
frontend/src/main.jsx          router: nav bar, / (App) and /analytics
frontend/src/App.jsx           Overview page: panels, client table, state chips
frontend/src/Analytics.jsx     Analytics page: comparison strip, CPA/CTR trends, ad set table
frontend/src/reportingWindow.js  ?window= URL state, shared by both pages
frontend/src/format.js         unit-aware value formatting, state labels
frontend/src/api.js            fetch wrappers
frontend/src/styles.css        the design system (tokens on :root)
frontend/src/components/
  NavBar.jsx                   app header: agency name + Overview / Analytics tabs
  WindowSelector.jsx           30 days / 90 days / All toggle
  TrendChart.jsx               one-metric daily line chart (Analytics)
  GoalCell.jsx                 pick a client's goal metric
  TargetCell.jsx               set the target, in that metric's units
  VitalsTrace.jsx              per-row sparkline of the goal metric
  HistoryPanel.jsx             expanded per-account chart
  PortfolioHistory.jsx         portfolio daily spend, time-scaled with gaps broken
```

## Scope fence
- **v1 (built):** multi-account dashboard, per-account KPIs, portfolio totals as
  the page heading.
- **Per-client target tracking (built).** Originally v2; the user explicitly
  authorised it on 2026-09-10.
- **Not built:** the needs-attention feed, alerting/notifications, deployment.
- **Analytics page (built, read-only).** Authorised by the user on 2026-09-11:
  period-over-period comparison, CPA and CTR trends, ad set breakdown for one
  client. No editing on this page.
- **No mobile version.** Desktop only, by the user's decision on 2026-09-11: no
  breakpoints, no viewport meta tag. Do not add a responsive layout.
- Do NOT build anything beyond this (extra dashboards, LLM features, write
  actions) without checking first. One finished MVP beats three in progress.

## Known defects
- **`conversions` was inflated — fixed 2026-09-13.** It summed *every* Meta
  action type, so results ran at roughly twice reality and every cost per result
  read half price. `results` now counts only the outcome each ad set optimises
  for (`ingest/results.py`), and an unmapped goal warns rather than guessing.
  The old column is still written but never read.
- The nightly GitHub Actions cron ran again on 2026-09-12 (a row for that date
  arrived on its own), so Meta's business verification did clear it. It runs
  `main`, so until this branch merges, nightly rows carry no `results` and no ad
  set detail — re-run the ingest for those dates after merging.

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
