# CLAUDE.md — Multi-Client Meta Ads Dashboard

Working notes for AI-assisted development on this repo: the architecture, the
rules that hold it together, and the conventions to follow. `README.md` is the
human-facing overview; `docs/DESIGN.md` describes the visual system.

## Project
A dashboard that pulls several Meta ad accounts into one normalised view. The
point over Meta's own Ads Manager is **cross-account aggregation**: one place,
every client, each measured against its own goal.

## Stack
- Python 3.11+: FastAPI backend and the ingest
- Ingest: `facebook-business` SDK
- Store: Postgres (Supabase) via SQLAlchemy Core. `DATABASE_URL` selects it;
  without it the code falls back to SQLite. SQLAlchemy is pinned below 2.1:
  2.1 maps a plain `postgresql://` URL to psycopg 3, and the project installs
  psycopg2.
- Frontend: React 18 + Vite + Recharts + React Router 7 (`BrowserRouter`), fonts
  self-hosted via `@fontsource`. Routes are real paths, so a static host must
  rewrite unknown paths to `index.html` or a direct `/analytics` link will 404.
- Deploy: a public demo on Render (`render.yaml`), API in demo mode. The nightly
  ingest runs from GitHub Actions against the real store.

**Local environment:** there is no venv on the maintainer's machine; the Python
dependencies live in `/opt/anaconda3/bin/python3`. Plain `python3` resolves
elsewhere and fails on `import sqlalchemy`.

## Architecture rules (load-bearing; discuss before changing)
- **Pull and store, never live-query.** A nightly job pulls each account's
  insights into Postgres, and the dashboard reads only from Postgres. Never
  call the Meta API on page load: it keeps rate limits irrelevant and the UI
  instant, and retains history Meta's interface discards.
- **Standard/Limited Access only.** Read accounts the agency owner has an
  admin/advertiser role on, under one system-user token. No multi-tenant login
  where third parties connect their own accounts: that needs Advanced Access
  and App Review.
- **Read-only against Meta.** `ads_read` scope only. Never implement anything
  that modifies a live campaign (pause, edit, budget). The only writes are to
  our own database: the ingest writes insights, campaigns and the heartbeat;
  the API writes only `account_targets`.

## Guardrails
- Anything rule-based is **alert-only**: when a threshold is breached it
  notifies, and never pauses or edits a campaign. Leave any action hook stubbed
  with a comment explaining why. Real client money is on these accounts.
- Secrets (Meta token, app secret, database URL) live in environment variables
  or a gitignored `.env` (template: `.env.example`). Never commit them.
- The nightly job uses a Meta **system-user token**. Plain user tokens expire
  after about 60 days and would silently break it.
- Never present sample or placeholder figures as real client data. Demo mode
  is labelled on screen as demo data.
- **Ingest logs are public** (the repo is public, so are its Actions logs).
  Print counts only, never spend, delivery or any other client figure, and mask
  account ids to their last four digits with `mask()` in `ingest/run.py`.

## Conventions
- **None, not zero, for missing data.** A rate with nothing to divide by, or a
  field that was never ingested, is `None`/null. Zero is a claim about
  performance; a gap is not one.
- **Bug fixes start with a failing test**, run to show it failing, then the fix.
- Python is formatted and linted with Ruff (`pyproject.toml`, pinned in
  `requirements-dev.txt`). CI fails on lint or format errors.
- Tests never touch the real database or Meta: `tests/conftest.py` pins dummy
  environment variables before importing the app, and the ingest tests replace
  the Meta SDK with a fake.

## Data model
`ingest/db.py` owns every table. `init_db()` runs `create_all` plus idempotent
`ALTER TABLE` statements for columns added after first ship: add new columns to
`_ADDED_COLUMNS` there, because `create_all` never alters an existing table.
The ingest calls `init_db()`; the API does not, so a fresh database has no
tables until the ingest has run (demo mode builds its own in memory).

**`daily_insights`**: one row per account per day, upserted idempotently.
| column | notes |
|---|---|
| `account_id`, `date` | composite primary key |
| `spend`, `impressions`, `clicks`, `conversions` | non-null |
| `reach` | nullable; unique people, distinct from impressions |
| `purchase_value` | nullable; revenue, for ROAS |
| `frequency` | nullable; impressions per person that day, as Meta calculated it. Pulled, never derived: it is impressions ÷ reach for the period asked for, and reach does not add up across days, so a week's frequency is not the mean of its days. Null wherever `reach` is null |
| `results` | nullable; each ad set's own optimisation outcome, summed for the day |
| `results_basis` | nullable; `action`, `reach`, `mixed` or `unmapped` |

`conversions` is the legacy sum of every Meta action type. It is still written,
so history stays intact, but nothing reads it: it counted unrelated outcomes
together and ran at roughly twice reality. `results` replaced it.

`reach` and `purchase_value` are nullable on purpose: rows ingested before those
fields were pulled have no value, and zero would be a lie rather than a gap.

**`account_targets`**: one row per client; the only table the API writes.
| column | notes |
|---|---|
| `account_id` | primary key |
| `client_name` | display name; falls back to the account id |
| `goal_metric` | which metric this client is judged on |
| `target_value` | the goal, in that metric's units |
| `period_start`, `period_end` | nullable; a goal period set by hand, which wins over campaign dates |
| `updated_at` | UTC |

A legacy `target_cpr` column may exist in older databases. It is unused;
`init_db()` copies any remaining value into `target_value`.

**`adset_daily_insights`**: one row per ad set per day, upserted idempotently by
the same ingest run. Feeds the Analytics breakdown; campaign totals are a
grouping of these rows.
| column | notes |
|---|---|
| `account_id`, `adset_id`, `date` | composite primary key |
| `adset_name`, `campaign_id`, `campaign_name` | kept per day; the API shows the latest names |
| `spend`, `impressions`, `clicks`, `conversions` | non-null; `conversions` is the legacy all-actions sum |
| `reach`, `optimization_goal`, `result_action_type`, `results`, `cost_per_result` | nullable; what this ad set optimises for, what that outcome is, and what Meta says it cost |

**`campaigns`**: each campaign's current state, refreshed on every run. A
snapshot, not a time series: it answers "what is live right now".
| column | notes |
|---|---|
| `account_id`, `campaign_id` | composite primary key |
| `name` | campaign name |
| `effective_status` | Meta's rollup, which already accounts for pauses above the campaign |
| `account_active` | false when the ad account itself is not active (`account_status` ≠ 1) |
| `start_time`, `stop_time` | nullable; the schedule a goal's pace is judged against. `stop_time` is null on open-ended campaigns |
| `updated_at` | UTC |

Campaigns Meta stops returning are deleted on the next run, so a vanished
campaign cannot go on being counted as active.

**`ingest_heartbeat`**: one row per job (`ingest`), rewritten by every run so
the database sees a write each night even with no delivery to store. Supabase's
free tier pauses a project it sees as idle, and a paused project once took the
ingest down.
| column | notes |
|---|---|
| `job` | primary key |
| `last_run_at` | UTC; written as soon as a run reaches the database |
| `last_success_at` | UTC; written only when a run finishes. Behind `last_run_at` means runs are failing |

## Goal metrics
Defined in `GOAL_METRICS` in `app/main.py`. Each carries a `label`, a `unit`
(`currency` / `count` / `ratio`) and a `direction`.

`direction` is load-bearing: for `leads`, `roas` and `reach` **higher is better**;
for `cost_per_lead` and `cost_per_result` **lower is better**. `_evaluate_rate()`
signs the deviation so positive always means *worse* regardless of direction.

`cumulative` is the other load-bearing flag. `leads` and `reach` accumulate over
a period, so their targets are **paced**: 24,000 reach is 40% delivered at 40%
elapsed. Rate metrics (`cost_per_result`, `cost_per_lead`, `roas`) cannot be
paced (a £2 cost per lead is not £0.80 at 40% elapsed), so they are compared
with their target directly and carry no `pace` block.

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
| `no_end_date` | cumulative target with no period end. **Never** fall back to comparing against the full target here; that is the misleading behaviour this replaced |
| `no_target`, `no_data` | no goal set; or a goal with no delivery (it has not fallen short, it has not run) |

`reach` sums daily reach over the window, which over-counts unique people across
days. It carries a `note` saying so. Analytics' cost per 1,000 reached divides by
that same summed reach, so the window figure reads slightly cheap for the same
reason; the per-day points on its chart are pulled per day and are exact.

For an account whose ad sets optimise for reach (`results_basis` of `reach`, or
`unmapped`), `cost_per_result`, `cost_per_lead` and `leads` return None rather
than a mislabelled figure: there is no conversion to price. Analytics prices
those clients per 1,000 people reached instead, and never calls it CPA.

## API (`app/main.py`)
- `GET /api/board?days=N`: everything the Overview page renders, in one read.
  `days` is 0–3650; `0` means all retained history. Per account: goal metric,
  target, actual, signed deviation, state, and a trend series already in the
  goal metric's units. `portfolio_history` is scoped to the same window as the
  tiles. `retention` (`days_stored`, `first_date`, `last_date`,
  `starts_after_window`) reports what the store holds, separately, so a window
  reaching back further than the record says so rather than silently showing a
  different range.
  `portfolio.active_campaigns` is live campaign state and cannot be windowed.
  The board does not display it (the row shows Spend, Accounts, CPM and On
  pace), but the figure stays, ready to return. It is None, never 0, when no
  campaign has ever been synced, and counts campaigns `_is_delivering()`
  accepts: ACTIVE alone is not enough, since a campaign whose flight ended
  reports ACTIVE until somebody pauses it.
  `portfolio.cpm` is spend ÷ impressions × 1000 over the window (impressions,
  not reach: they add up across days and exist whatever the objective).
  `on_pace` / `pace_judged` / `pace_excluded` count clients meeting their pace
  out of those whose pace can be judged at all.
- `GET /api/analytics?account_id=…&days=N`: one client, read-only: totals for
  the window and the equal-length period before it (none when `days=0`), signed
  changes, daily CPA / cost-per-1,000-reached / CTR / frequency series, and the
  ad set breakdown. `has_conversion_spend` and `has_awareness_spend` say which
  cost stats mean anything. Omitting `account_id` picks the first known account.
- `GET /api/metrics`: the goal metrics on offer, so the UI cannot drift from
  what the server accepts.
- `GET /api/config`: `{"demo": bool}`, which drives the demo-data banner.
- `PUT /api/targets/{account_id}`: set a client's goal metric, target and
  optional period. Rejects an unknown metric, a target ≤ 0, and a period that
  ends before it starts.

## Key components
```
ingest/run.py          Meta pull: campaign state, then account + ad set
                       insights; yesterday by default, --days/--since to backfill
ingest/db.py           schema, migrations, idempotent upserts, heartbeat
ingest/results.py      optimisation goal → what counts as a result
app/main.py            API, goal-metric registry, state evaluation
app/demo.py            seeded fictional portfolio for DEMO_MODE
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
  LoadingNotice.jsx            loading state, e.g. while the free-tier API wakes
  TrendChart.jsx               one-metric daily line chart (Analytics)
  GoalCell.jsx                 pick a client's goal metric
  TargetCell.jsx               set the target, in that metric's units
  VitalsTrace.jsx              per-row sparkline of the goal metric
  HistoryPanel.jsx             expanded per-account chart
  PortfolioHistory.jsx         portfolio daily spend, time-scaled with gaps broken
tests/                         pytest suite; see README for what each file covers
```

## Scope
- **Built:** the multi-account Overview with portfolio totals and per-client
  goals, targets and pace; the read-only Analytics page (period-over-period
  comparison, CPA/CTR trends, ad set breakdown for one client); demo mode.
- **Not built:** a needs-attention feed and alerting/notifications.
- **Desktop only.** No breakpoints and no viewport meta tag; do not add a
  responsive layout.
- Check before building anything beyond this (extra dashboards, LLM features,
  write actions). One finished product beats three in progress.

## Commands
- Install (Python): `/opt/anaconda3/bin/python3 -m pip install -r requirements.txt -r requirements-dev.txt`
- Install (frontend): `npm --prefix frontend install`
- Demo API: `DEMO_MODE=true /opt/anaconda3/bin/python3 -m uvicorn app.main:app`
- Ingest yesterday: `/opt/anaconda3/bin/python3 -m ingest.run`
- Backfill: `... -m ingest.run --days 90` or `--since 2026-06-01 --until 2026-09-09`
- API (dev): `/opt/anaconda3/bin/python3 -m uvicorn app.main:app --reload`
- Frontend (dev): `npm --prefix frontend run dev` (port 5173, proxies `/api` to
  port 8000)
- Tests: `/opt/anaconda3/bin/python3 -m pytest`. In-memory SQLite locally; CI
  (`.github/workflows/tests.yml`) runs them against a Postgres container via
  `TEST_DATABASE_URL`.
- Format and lint: `/opt/anaconda3/bin/python3 -m ruff format .` and
  `... -m ruff check .`

## Verification
- After changing ingest logic, run the tests in `tests/test_ingest.py`, then a
  manual pull, and confirm rows land in Postgres. There is only one real ad
  account, so a two-account check against live data is not possible; the demo
  portfolio covers multi-account behaviour.
- Confirm the dashboard renders from the database with Meta unreachable.
- Thin and empty states are the common case here, not the edge: one real
  account, little data, nothing recent. Check them.
