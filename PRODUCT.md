# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Backend exists and is settled: Python 3.11+, FastAPI, SQLAlchemy, Supabase Postgres, `facebook-business` SDK for ingest.

Frontend: **React + Recharts**, per `SPEC.md`. The user was offered the Streamlit fallback that `SPEC.md` reserves for calendar pressure and declined it — *"i want a working front end, dont worry about the deadline too much that's for me. lets make this good."* Stack choice is therefore **delegated**: React + Recharts confirmed as the spec's original selection, chosen for design control over speed. No frontend scaffold exists yet.

## Users

**There is exactly one user: the agency operator** (Sam Griffiths, SG Digital Marketing), checking on several client Meta ad accounts at once. Works alone; is both the person who buys the ads and the person who reports on them. Corrected 2026-09-10 — an earlier reading of this file treated interviewers as a second audience, and the user rejected it: *"this is something for only me to use and then im just going to do a video demo."*

**Nobody else ever operates the interface.** The September 2026 demo is a **recorded video**, not a live walkthrough and not a handover. So the surface owes no self-introduction: no nameplate, no product title bar, no explanatory colophon, no orientation copy written for a stranger. The operator already knows what they are looking at, and a video viewer is watching, not driving. Density and directness beat legibility-to-an-outsider wherever the two conflict.

**Explicitly not users: the agency's own clients.** They never log in. Third-party multi-tenant access is out of scope (`CLAUDE.md`), and no client-facing or screen-share use was confirmed.

## Product Purpose

Pull multiple Meta ad accounts into one normalised view so the operator can see every client's performance from a single login.

Meta's native Ads Manager is built around one advertiser managing one account — one dashboard per account, no unified cross-account view. This product does the thing Meta's suite structurally cannot.

**Success, on an ordinary day:** the operator opens it and learns *how everything is doing overall.* The portfolio roll-up is the headline; per-account detail is supporting evidence, not the main event. This was confirmed directly and should outrank contrary instincts about dashboard convention.

**Success, at the demo:** a stranger understands the cross-account thesis from the screen, without narration.

## Positioning

**Cross-account aggregation under one login.** A neighbouring product built on Meta's own surface cannot truthfully claim it, because Meta has no cross-account view to begin with.

The discipline that protects this claim: it is *aggregation*, not cross-industry *comparison*. Ranking a nursery's cost-per-acquisition against a plumber's is meaningless and must never be built. Accounts are totalled together, and (in v2) each is measured against **its own target** — never against each other.

## Operating Context

- **Pull-and-store, never live-query.** A scheduled job pulls each account's daily insights into Postgres. The dashboard reads *only* from Postgres and never calls Meta on page load. This makes rate limits irrelevant, keeps the UI instant, and retains history Meta's own UI discards.
- **Ingest is currently manual.** `python -m ingest.run` (add `--days N` or `--since/--until` to backfill a range). The nightly GitHub Actions cron is written and committed but was blocked by Meta pending business verification. Verification was completed 2026-09-10 and API access is restored; whether the cron now works from cloud IPs is **untested**.
- **Deployment must be a live URL** (Render or Railway), not a local script.
- Project dependencies live in the Anaconda Python at `/opt/anaconda3/bin/python3`, not the system `python3`. There is no virtualenv.

## Capabilities and Constraints

**Load-bearing rules (from `CLAUDE.md`, do not deviate without asking):**
- **Read-only against Meta.** `ads_read` scope only. Never implement write operations that modify live campaigns — no pause, edit, or budget changes.
- **The rules engine is alert-only.** When a threshold is breached it notifies; it does not act. Real client money is on these accounts. Any action hook stays stubbed.
- **Standard/Limited Access only**, under a single long-lived system-user token. No third-party connect-your-own-account flow.
- Secrets live in a gitignored `.env`; never committed.

**Current shape:**
- Store: Supabase Postgres via `DATABASE_URL`. The committed `dashboard.db` SQLite file is a **stale leftover**, not the live store, and holds a duplicate of one old row.
- Schema: `daily_insights(account_id, date, spend, impressions, clicks, conversions)`, primary key `(account_id, date)`, idempotent upsert — re-running ingest over the same dates is safe.
- API: `GET /accounts` (per-account totals, CTR, CPR, and a daily trend series) and `GET /portfolio` (month-to-date spend, conversions, account count).
- Currency: GBP.

**Terminology:** *CPR* = cost per result = spend ÷ conversions. *CTR* = clicks ÷ impressions × 100. "Result" and "conversion" are used interchangeably.

**Known defect, undecided:** the ingest sums the value of *every* Meta action type (link clicks, post engagement, video views) into `conversions`, so the figure is inflated — the stored data shows more conversions than clicks on most days. CPR is consequently around twice as favourable as reality. This is the headline number on the dashboard. Not yet fixed; the fix has not been scoped.

## Scope Fence

**v1:** multi-account dashboard, per-account KPIs (spend, CPR, CTR, conversions, trend), plus a portfolio roll-up header showing totals across all accounts.

**v2:** per-account target tracking (each client against its own goal, pace vs target) and a "needs-attention" feed for accounts that breached a threshold or moved sharply week-on-week.

**Explicitly out of scope:** cross-industry ranking, auto-pausing or editing campaigns, multi-tenant third-party login, extra dashboards, LLM features. One finished MVP beats three in progress.

## Brand Commitments

The agency is named **SG Digital Marketing** (confirmed — it is the live Meta ad account name).

No logo, wordmark, palette, typeface, or brand assets exist or were provided. No voice or personality has been established. Future work must not invent brand assets and present them as existing ones.

## Evidence on Hand

**Real data, verified in Postgres 2026-09-10:**
- **One** ad account: `act_1787458649299492`, "SG Digital Marketing", GBP, active.
- **8 days** of insights, 2026-07-04 to 2026-07-11 — this is the account's entire delivery history, confirmed by backfilling from January and getting only these rows.
- Totals across that window: £34.37 spend, 26,486 impressions, 41 clicks, 87 conversions.
- **No data for September.** `GET /portfolio` filters to the current calendar month, so it currently returns zeros.

**Open dependency (`SPEC.md`):** a second account is needed before the demo or the cross-account thesis is invisible on screen — a single-account view cannot demonstrate aggregation. Not yet obtained.

**Absences that must not be fabricated:** there are no clients beyond the one account, no testimonials, no case studies, no benchmarks, no press, no pricing, and no usage numbers. Sample or placeholder data must never be presented as real client data.

## Product Principles

1. **The roll-up is the headline.** Portfolio health answers the daily question; per-account detail is evidence beneath it. Resist the convention of leading with a grid of equal account cards.
2. **Aggregate, never rank clients against each other.** Comparison across industries is meaningless. Each account is judged against its own target.
3. **Never act on client money.** Alerts inform; they never pause, edit, or spend. Read-only against Meta is absolute.
4. **Read from the store, never from Meta at render time.** The interface must remain fully functional with Meta unreachable — this is the property the whole architecture was chosen for.
5. **Be honest about thin data.** With one account and eight days of history, empty states, zero states, and single-point trends are not edge cases — they are the common case, and the interface must handle them with dignity rather than disguise them.
