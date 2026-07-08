# SPEC — Multi-Client Meta Ads Dashboard

## What this is
An agency-style dashboard that pulls several Meta ad accounts into one place,
normalises them, and shows performance across all of them from a single login.

## Why it exists (the design constraint)
Meta's native suite is built for one advertiser managing one account — one
dashboard per account, no unified cross-account view. This tool does the thing
Meta's suite structurally cannot: **aggregate multiple client accounts into one
normalised view**. If someone asks "why not just use Meta's suite?", the answer
is that Meta has no cross-account view — which is genuinely true and is the
point of the project.

Note on scope discipline: this is *aggregation*, not cross-industry *comparison*.
Ranking a nursery's CPA against a plumber's CPA is meaningless. We aggregate
(all clients, one view, one roll-up) and, in v2, measure each account against
**its own target** — never against each other.

## Feasibility (settled)
- The Meta Marketing API is free — reading spend/impressions/clicks/conversions
  costs nothing. No LLM in the core.
- Standard/Limited Access (instant on app creation) is sufficient: it can read
  any ad account the app owner has an admin/advertiser role on. Advanced Access
  (App Review + business verification) is only needed for a multi-tenant product
  where third parties connect their own accounts — out of scope for v1.
- Rate limits are spend-based and a non-issue because of pull-and-store: a
  nightly pull of a few small accounts is nowhere near any ceiling.

## Architecture
Nightly GitHub Actions job → `facebook-business` SDK pulls each account's daily
insights → normalised into Postgres → FastAPI serves the data → React dashboard
reads from the API. The dashboard never calls Meta directly. Benefits: rate
limits irrelevant, instant UI, retained history Meta discards, and any optional
LLM summary is one cheap call over stored data.

## Features (ranked, MVP-first)
MUST (v1 — stop here and it still ships as a real differentiator):
1. Multi-account ingest into one normalised schema.
2. Per-account KPI dashboard: spend, cost-per-result, CTR, conversions, trend.
3. Portfolio roll-up header: totals across all accounts (spend, conversions,
   this-month). This is the single clearest "not Ads Manager" signal.

SHOULD (v2 view):
4. Per-account **target tracking** — set a target CPR/CPA per client, show
   pace-vs-target (green/red). Strongest feature in the project: correct
   normalisation, impossible in Meta's suite, pure "builder encoded agency logic"
   signal.
5. "Needs-attention" feed — accounts that breached a threshold or moved sharply
   week-on-week. This is the alert engine surfaced as a view.

COULD (only if ahead of schedule):
6. One cheap LLM "explain this week" summary per report. Optional, cost-capped.

Explicitly NOT in scope: cross-industry ranking, auto-pausing/editing live
campaigns, multi-tenant third-party login.

## Tech stack
- Language: Python
- Ingest: `facebook-business` SDK + pandas, run via GitHub Actions cron
- Store: Postgres (Supabase free tier); SQLite ok for first local iteration
- Backend: FastAPI
- Frontend: React + Recharts (Streamlit is the fallback only if the calendar
  forces it)
- Deploy: Render or Railway — live URL required
- Auth to Meta: single system-user token (long-lived), `ads_read` scope only

## Milestones (working back from a September 2026 demo, ~8 weeks)
Hard gates: auth proven by end of Week 1; MVP deployed by end of Week 4.

- **Week 1 — De-risk auth.** Business-type dev app, enable Marketing API, set up
  Business Manager, generate a system-user token, and a script that pulls
  yesterday's spend/impressions/clicks/conversions for TWO accounts and prints
  them. Riskiest part — prove it before building anything on top.
- **Week 2 — Ingest → store.** Nightly pull landing normalised daily rows in
  Postgres.
- **Weeks 3–4 — Cross-account dashboard, deployed live.** Per-account KPIs +
  portfolio roll-up. This is the MVP; protect this line above everything.
- **Week 5 — v2 view.** Per-account target tracking + needs-attention feed
  (alert-only).
- **Week 6 — README, deploy hardening, interview-narrative doc** (write down the
  "why not just use Meta" story).
- **Weeks 7–8 — Buffer + optional LLM summary.**

## Open dependency
Need at least TWO accounts of real data before the demo, or the cross-account
thesis is invisible on screen. Priority: a second real micro-client (best — grows
the agency too), else own personal ad account, else a Meta test account.
