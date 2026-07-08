# CLAUDE.md — Multi-Client Meta Ads Dashboard

## Project
Agency-style dashboard that pulls multiple Meta ad accounts into one normalised
view. The differentiator over Meta's native Ads Manager is **cross-account
aggregation** — one login, all clients, normalised. Full context in `SPEC.md`.
Read `SPEC.md` before starting a new milestone.

## Stack
- Python 3.11+ throughout
- Ingest: `facebook-business` SDK + pandas
- Scheduler: GitHub Actions scheduled workflow (nightly cron)
- Store: Postgres (Supabase free tier). SQLite acceptable for early local dev.
- Backend: FastAPI
- Frontend: React + Recharts
- Deploy: Render or Railway (must be a live URL, not a local script)

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

## Guardrails
- The rules engine is **alert-only**. When a threshold is breached, it notifies —
  it does NOT pause or edit campaigns. Leave any action hook stubbed with a
  comment explaining the deliberate choice. Real client money is on these
  accounts; auto-acting is a foot-gun.
- Secrets (Meta system-user token, app secret, DB URL) live in environment
  variables / a gitignored `.env`. NEVER commit tokens or secrets.
- Use a Meta **system-user token** for the nightly job (long-lived). Plain user
  tokens expire in ~60 days and will silently break automation.

## Scope fence
- **v1:** multi-account dashboard, per-account KPIs (spend, CPR, CTR,
  conversions, trend) + a **portfolio roll-up header** (totals across all
  accounts).
- **v2 view:** "needs-attention" — per-account performance vs its own target
  (each client compared to its own goal, not to other clients).
- Do NOT build anything beyond this (extra dashboards, LLM features, write
  actions) without checking first. One finished MVP beats three in progress.

## Commands
<!-- Fill in as the project takes shape -->
- Install: `pip install -r requirements.txt`
- Run ingest (manual): `python -m ingest.run`
- Run API (dev): `uvicorn app.main:app --reload`
- Frontend (dev): `npm run dev`

## Verification
- After changing ingest logic, run a manual pull against two test accounts and
  confirm rows land in Postgres before moving on.
- Confirm the dashboard renders from the DB with the API disconnected from Meta.
