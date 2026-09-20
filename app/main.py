"""FastAPI backend. Reads only from Postgres — never calls Meta directly
(see CLAUDE.md architecture rules).
"""
import os
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ingest.db import (
    account_targets,
    adset_daily_insights,
    campaigns,
    daily_insights,
    get_engine,
    upsert_account_target,
)
from ingest.results import result_label
from app.demo import DEMO_MODE, build_demo_engine

load_dotenv()
app = FastAPI(title="Meta Agency Dashboard")

# The whole demo switch, in one place. In demo mode the API talks to an
# in-memory database holding a fictional portfolio, so every route below runs
# unchanged and the real store is never opened — DATABASE_URL is not read, and
# no request can reach a real client's figures.
engine = build_demo_engine() if DEMO_MODE else get_engine()

# The dashboard is served from a separate dev server in development, and from a
# separate host entirely once deployed. Both are named explicitly: never a
# wildcard, which would let any page on the internet read this API.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def _deployed_origins():
    """The deployed frontend's origin, from FRONTEND_ORIGIN.

    Comma-separated, so a second host (a custom domain alongside the default
    one) needs no code change. Unset — the local case — yields nothing, leaving
    the dev origins exactly as they were. A bare hostname is accepted because
    that is the form Render passes one service's address to another in.
    """
    origins = []
    for item in os.environ.get("FRONTEND_ORIGIN", "").split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        if not origin.startswith(("http://", "https://")):
            origin = f"https://{origin}"
        if origin not in origins:
            origins.append(origin)
    return origins


ALLOWED_ORIGINS = DEV_ORIGINS + [o for o in _deployed_origins() if o not in DEV_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The metrics a client can be measured on. `direction` says which way is good,
# which the UI needs in order to colour the correct end of the progress bar:
# missing a leads target is a shortfall, missing a cost target is an overspend.
# Alert-only throughout — breaching a target notifies, it never touches a
# campaign (CLAUDE.md).
# `cumulative` marks a metric that accumulates over a period, so a target for it
# can be paced: 24,000 reach is 40% delivered at 40% elapsed. A rate metric
# cannot — a £2 cost per lead is not £0.80 at 40% elapsed — so those are judged
# against their target directly, with no time dimension.
GOAL_METRICS = {
    "leads": {"label": "Leads", "unit": "count", "direction": "higher", "cumulative": True},
    "roas": {"label": "ROAS", "unit": "ratio", "direction": "higher"},
    "cost_per_lead": {"label": "Cost per lead", "unit": "currency", "direction": "lower"},
    "cost_per_result": {
        "label": "Cost per result",
        "unit": "currency",
        "direction": "lower",
    },
    "reach": {
        "label": "Reach",
        "unit": "count",
        "direction": "higher",
        "cumulative": True,
        # Daily reach summed over the window. Meta deduplicates people within a
        # day but not across days, so this over-counts unique reach.
        "note": "summed daily reach, not deduplicated across days",
    },
}

DEFAULT_GOAL_METRIC = "cost_per_result"

# Delivering at least this share of the pace a target implies is "at risk";
# below it is "behind". At or above the full pace is "on track".
AT_RISK_PACE = 0.85


def _ctr(clicks: int, impressions: int) -> float:
    return round(clicks / impressions * 100, 2) if impressions else 0.0


class TargetIn(BaseModel):
    client_name: str | None = Field(default=None, max_length=200)
    goal_metric: str | None = Field(default=None)
    target_value: float | None = Field(default=None, gt=0)
    # The period a cumulative target applies to, for clients whose campaigns
    # carry no stop time. Omitted fields leave any existing period alone.
    period_start: date | None = Field(default=None)
    period_end: date | None = Field(default=None)


def _metric_actual(metric: str, spend: float, results: int | None, reach: int | None,
                   revenue: float | None, results_basis: str | None) -> float | None:
    """This client's goal metric over the window, or None when the underlying
    data was never ingested — which must stay distinct from a value of zero.

    `results` counts each ad set's own optimisation outcome (ingest/results.py).
    When that outcome is reach, a cost per result or a lead count would be a
    mislabelled figure rather than a small one, so those metrics return None.
    """
    if metric in ("cost_per_result", "cost_per_lead", "leads"):
        if results is None or results_basis in ("reach", "unmapped"):
            return None
        if metric == "leads":
            return float(results)
        return round(spend / results, 2) if results else None
    if metric == "roas":
        if revenue is None or not spend:
            return None
        return round(revenue / spend, 2)
    if metric == "reach":
        return float(reach) if reach is not None else None
    return None


def _metric_point(metric: str, row) -> float | None:
    """The same metric for a single day, for the trend series."""
    return _metric_actual(
        metric,
        row.spend,
        row.results,
        row.reach,
        row.purchase_value,
        row.results_basis,
    )


def _basis(lowest: str | None, highest: str | None) -> str | None:
    """One basis for a span of days: the shared one, or "mixed"."""
    if lowest is None:
        return None
    return lowest if lowest == highest else "mixed"


def _evaluate_rate(metric: str, target: float, actual: float | None):
    """A rate goal — cost per result, cost per lead, ROAS — against its target.
    There is no pace to judge: the target is the rate itself, at any moment in
    the period. Deviation is signed so positive always means worse.
    """
    if actual is None:
        return "no_data", None

    direction = GOAL_METRICS.get(metric, {}).get("direction", "lower")
    deviation = (
        (actual - target) / target if direction == "lower" else (target - actual) / target
    )
    state = "behind" if deviation > 0 else "on_track"
    return state, round(deviation, 4)


def _goal_period(conn, account_id: str, target_row, today: date):
    """(start, end, source) for the period a cumulative target applies to.

    A period set by hand wins. Otherwise the campaigns running today define it,
    so a client with an old finished campaign and a current one is judged on the
    current one. With nothing running, the most recently finished campaign is
    used, which is what lets a goal read met or missed. A campaign with no stop
    time is open-ended and cannot be paced at all.
    """
    if target_row is not None and getattr(target_row, "period_end", None) is not None:
        return target_row.period_start, target_row.period_end, "manual"

    dated = [
        (row.start_time.date(), row.stop_time.date())
        for row in conn.execute(
            select(campaigns.c.start_time, campaigns.c.stop_time).where(
                campaigns.c.account_id == account_id,
                campaigns.c.effective_status == "ACTIVE",
                campaigns.c.account_active.is_(True),
            )
        ).all()
        if row.start_time is not None and row.stop_time is not None
    ]
    if not dated:
        return None, None, None

    running = [(start, end) for start, end in dated if start <= today <= end]
    if running:
        return min(s for s, _ in running), max(e for _, e in running), "campaigns"

    finished = [(start, end) for start, end in dated if end < today]
    if finished:
        latest = max(e for _, e in finished)
        return min(s for s, e in finished if e == latest), latest, "campaigns"

    starts_next = min(dated, key=lambda period: period[0])
    return starts_next[0], starts_next[1], "campaigns"


def _pace(target: float, actual: float, start: date, end: date, today: date) -> dict:
    """Progress against the pace the target implies, rather than against its
    total. Whole days throughout, and the elapsed share is clamped to 0–1.
    """
    total_days = (end - start).days + 1
    elapsed_days = min(max((today - start).days + 1, 0), total_days)
    elapsed_fraction = elapsed_days / total_days
    expected = round(target * elapsed_fraction, 2)

    return {
        "period_start": str(start),
        "period_end": str(end),
        "total_days": total_days,
        "elapsed_days": elapsed_days,
        "days_left": max((end - today).days, 0),
        "elapsed_fraction": round(elapsed_fraction, 4),
        "expected_to_date": expected,
        "pace_ratio": round(actual / expected, 4) if expected else None,
        # The period's own figure, not the window the board happens to show, so
        # switching 30/90/All never changes the state.
        "period_actual": actual,
        "ended": today > end,
    }


def _state_from_pace(pace: dict, target: float, actual: float):
    """State and signed deviation from pace. Deviation stays positive-is-worse:
    here it is the shortfall against what should have been delivered by now.
    """
    if pace["ended"]:
        return ("met", None) if actual >= target else ("missed", None)

    ratio = pace["pace_ratio"]
    if ratio is None:  # the period has not started, so nothing is due yet
        return "not_started", None

    deviation = round(1 - ratio, 4)
    if ratio >= 1.0:
        return "on_track", deviation
    if ratio >= AT_RISK_PACE:
        return "at_risk", deviation
    return "behind", deviation


def _metric_over_period(conn, account_id: str, metric: str, start: date, end: date):
    """This client's goal metric over its own period, which is what a pace
    judgement has to be made against.
    """
    spend, results, reach, revenue, basis_low, basis_high = conn.execute(
        select(
            func.coalesce(func.sum(daily_insights.c.spend), 0.0),
            func.sum(daily_insights.c.results),
            func.sum(daily_insights.c.reach),
            func.sum(daily_insights.c.purchase_value),
            func.min(daily_insights.c.results_basis),
            func.max(daily_insights.c.results_basis),
        ).where(
            daily_insights.c.account_id == account_id,
            daily_insights.c.date >= start,
            daily_insights.c.date <= end,
        )
    ).one()

    return _metric_actual(
        metric,
        spend,
        int(results) if results is not None else None,
        reach,
        revenue,
        _basis(basis_low, basis_high),
    )


# States that put an account on the board's attention count.
ATTENTION_STATES = {"behind", "at_risk", "missed", "no_data"}

# Pace health. A client whose pace cannot be judged at all — no period end, no
# target, no delivery, not started — is excluded from both halves of the count
# rather than counted as a failure.
PACE_HEALTHY = {"on_track", "met"}
PACE_JUDGED = PACE_HEALTHY | {"at_risk", "behind", "missed"}

# How recently a campaign must have delivered to count as running. A week is
# long enough to survive a quiet weekend or a day the ingest missed.
RECENT_DELIVERY = timedelta(days=7)


def _is_delivering(campaign, delivering_ids: set[str], today: date) -> bool:
    """Whether a campaign is actually running.

    `effective_status` alone cannot answer this: a campaign whose flight ended
    keeps reporting ACTIVE forever if nobody paused it, which is why the board
    counted a campaign that finished ten weeks ago. "Active" is a judgement
    call, so it is made here and nowhere else.

    Counted when Meta says ACTIVE on a live account, the flight has not ended,
    and either it delivered impressions in the last week or it is too newly
    started (or scheduled too late) to have delivered any yet.
    """
    if campaign.effective_status != "ACTIVE" or not campaign.account_active:
        return False
    if campaign.stop_time is not None and campaign.stop_time.date() < today:
        return False
    if campaign.campaign_id in delivering_ids:
        return True
    return (
        campaign.start_time is not None
        and campaign.start_time.date() >= today - RECENT_DELIVERY
    )


@app.get("/api/board")
def board(days: int = 30):
    """Everything the dashboard renders, in one read from Postgres.

    `days=0` widens the window to all retained history — the history Meta's
    own interface discards.
    """
    if days < 0:
        raise HTTPException(status_code=422, detail="days must be 0 or greater")

    today = date.today()
    since = None if days == 0 else today - timedelta(days=days - 1)

    with engine.connect() as conn:
        known = set(
            conn.execute(select(daily_insights.c.account_id).distinct()).scalars().all()
        )
        target_rows = {
            row.account_id: row
            for row in conn.execute(
                select(
                    account_targets.c.account_id,
                    account_targets.c.client_name,
                    account_targets.c.goal_metric,
                    account_targets.c.target_value,
                )
            ).all()
        }
        known |= set(target_rows)

        accounts = []
        for account_id in sorted(known):
            scoped = [daily_insights.c.account_id == account_id]
            if since is not None:
                scoped.append(daily_insights.c.date >= since)

            (
                spend,
                impressions,
                clicks,
                results,
                reach,
                revenue,
                basis_low,
                basis_high,
            ) = conn.execute(
                select(
                    func.coalesce(func.sum(daily_insights.c.spend), 0.0),
                    func.coalesce(func.sum(daily_insights.c.impressions), 0),
                    func.coalesce(func.sum(daily_insights.c.clicks), 0),
                    func.sum(daily_insights.c.results),
                    func.sum(daily_insights.c.reach),
                    func.sum(daily_insights.c.purchase_value),
                    func.min(daily_insights.c.results_basis),
                    func.max(daily_insights.c.results_basis),
                ).where(*scoped)
            ).one()
            results = int(results) if results is not None else None
            results_basis = _basis(basis_low, basis_high)

            latest = conn.execute(
                select(func.max(daily_insights.c.date)).where(
                    daily_insights.c.account_id == account_id
                )
            ).scalar()

            target_row = target_rows.get(account_id)
            metric = (target_row.goal_metric if target_row else None) or DEFAULT_GOAL_METRIC
            metric_spec = GOAL_METRICS.get(metric, GOAL_METRICS[DEFAULT_GOAL_METRIC])
            target = target_row.target_value if target_row else None

            trend_rows = conn.execute(
                select(
                    daily_insights.c.date,
                    daily_insights.c.spend,
                    daily_insights.c.results,
                    daily_insights.c.results_basis,
                    daily_insights.c.reach,
                    daily_insights.c.purchase_value,
                )
                .where(*scoped)
                .order_by(daily_insights.c.date)
            ).all()

            # One series, in the units of this client's own goal metric.
            trend = [
                {
                    "date": str(row.date),
                    "value": _metric_point(metric, row),
                    "spend": round(row.spend, 2),
                    "results": row.results,
                }
                for row in trend_rows
            ]

            actual = _metric_actual(metric, spend, results, reach, revenue, results_basis)

            # Pace, not total. A cumulative goal is judged on how much of its
            # period has run; without a period end there is no pace to judge, and
            # comparing against the full target would be the misleading thing
            # this replaced.
            pace = None
            if target is None:
                state, deviation = "no_target", None
            elif not metric_spec.get("cumulative"):
                state, deviation = _evaluate_rate(metric, target, actual)
            else:
                period_start, period_end, period_source = _goal_period(
                    conn, account_id, target_row, today
                )
                if period_end is None:
                    state, deviation = "no_end_date", None
                else:
                    period_actual = _metric_over_period(
                        conn, account_id, metric, period_start, min(today, period_end)
                    )
                    if period_actual is None:
                        state, deviation = "no_data", None
                    else:
                        pace = _pace(target, period_actual, period_start, period_end, today)
                        pace["source"] = period_source
                        state, deviation = _state_from_pace(pace, target, period_actual)

            days_since = (today - latest).days if latest else None

            accounts.append({
                "account_id": account_id,
                "client_name": (target_row.client_name if target_row else None) or account_id,
                "goal_metric": metric,
                "goal_label": metric_spec["label"],
                "goal_unit": metric_spec["unit"],
                "goal_direction": metric_spec["direction"],
                "goal_note": metric_spec.get("note"),
                "target_value": target,
                "actual_value": actual,
                # Signed drift from this account's own goal, as a proportion.
                # Positive always means worse, whichever way the metric runs.
                "deviation": deviation,
                "state": state,
                # Null for a rate goal, or when there is no period to judge.
                "pace": pace,
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                # Each ad set's own optimisation outcome, not every action type
                # added together. "reach" basis means these are people reached.
                "results": results,
                "results_basis": results_basis,
                "reach": int(reach) if reach is not None else None,
                "purchase_value": round(revenue, 2) if revenue is not None else None,
                "ctr": _ctr(clicks, impressions),
                "last_data_date": str(latest) if latest else None,
                "days_since_data": days_since,
                "trend": trend,
            })

        portfolio_since = since
        totals_scope = [] if portfolio_since is None else [
            daily_insights.c.date >= portfolio_since
        ]
        total_spend, total_results, total_impressions, total_low, total_high = conn.execute(
            select(
                func.coalesce(func.sum(daily_insights.c.spend), 0.0),
                func.sum(daily_insights.c.results),
                func.coalesce(func.sum(daily_insights.c.impressions), 0),
                func.min(daily_insights.c.results_basis),
                func.max(daily_insights.c.results_basis),
            ).where(*totals_scope)
        ).one()

        # Impressions, deliberately, not reach: they add up across days and every
        # campaign has them whatever it optimises for, so this figure stays valid
        # for a portfolio mixing reach, leads and conversions.
        cpm = (
            round(total_spend / total_impressions * 1000, 2) if total_impressions else None
        )
        latest_overall = conn.execute(select(func.max(daily_insights.c.date))).scalar()

        # Live campaign state, not a windowed figure. None rather than zero
        # when no campaign has ever been synced: unknown is not "none active".
        campaign_rows = conn.execute(
            select(
                campaigns.c.campaign_id,
                campaigns.c.effective_status,
                campaigns.c.account_active,
                campaigns.c.start_time,
                campaigns.c.stop_time,
            )
        ).all()
        delivering_ids = {
            row.campaign_id
            for row in conn.execute(
                select(adset_daily_insights.c.campaign_id)
                .where(adset_daily_insights.c.date >= today - RECENT_DELIVERY)
                .group_by(adset_daily_insights.c.campaign_id)
                .having(func.sum(adset_daily_insights.c.impressions) > 0)
            ).all()
        }
        active_campaigns = (
            sum(1 for row in campaign_rows if _is_delivering(row, delivering_ids, today))
            if campaign_rows
            else None
        )

        # Scoped to the selected window, like the tiles above it, so the whole
        # Portfolio totals panel describes one range. What is stored is reported
        # separately as `retention` rather than silently widening this series.
        portfolio_history = [
            {
                "date": str(row.date),
                "spend": round(row.spend, 2),
                "results": row.results,
                "accounts": row.accounts,
            }
            for row in conn.execute(
                select(
                    daily_insights.c.date,
                    func.sum(daily_insights.c.spend).label("spend"),
                    func.sum(daily_insights.c.results).label("results"),
                    func.count(func.distinct(daily_insights.c.account_id)).label("accounts"),
                )
                .where(*totals_scope)
                .group_by(daily_insights.c.date)
                .order_by(daily_insights.c.date)
            ).all()
        ]

        # What the store actually holds, whatever window is selected. The board
        # says this out loud when the window reaches back further than the
        # record, instead of quietly showing a different range.
        stored_days, stored_first, stored_last = conn.execute(
            select(
                func.count(func.distinct(daily_insights.c.date)),
                func.min(daily_insights.c.date),
                func.max(daily_insights.c.date),
            )
        ).one()

    needing = [a for a in accounts if a["state"] in ATTENTION_STATES]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {
            "days": days,
            "since": str(since) if since else None,
            "until": str(today),
            "label": "all retained history" if days == 0 else f"the last {days} days",
        },
        "portfolio": {
            "active_campaigns": active_campaigns,
            "accounts_tracked": len(accounts),
            "cpm": cpm,
            "impressions": int(total_impressions),
            # Clients meeting their pace, out of those whose pace can be judged.
            "on_pace": sum(1 for a in accounts if a["state"] in PACE_HEALTHY),
            "pace_judged": sum(1 for a in accounts if a["state"] in PACE_JUDGED),
            "pace_excluded": sum(1 for a in accounts if a["state"] not in PACE_JUDGED),
            "accounts_needing_attention": len(needing),
            "accounts_behind": sum(1 for a in accounts if a["state"] == "behind"),
            "accounts_untargeted": sum(
                1 for a in accounts if a["target_value"] is None
            ),
            "spend": round(total_spend, 2),
            "results": int(total_results) if total_results is not None else None,
            "results_basis": _basis(total_low, total_high),
            "last_data_date": str(latest_overall) if latest_overall else None,
        },
        "portfolio_history": portfolio_history,
        "retention": {
            "days_stored": stored_days,
            "first_date": str(stored_first) if stored_first else None,
            "last_date": str(stored_last) if stored_last else None,
            # True when the window starts before anything on record, so the
            # series cannot fill it however long the window is.
            "starts_after_window": bool(since and stored_first and stored_first > since),
        },
        "accounts": accounts,
    }


@app.get("/api/config")
def config():
    """What the UI needs to know about this instance before it renders anything.
    `demo` drives the banner that marks the data as fictional.
    """
    return {"demo": DEMO_MODE}


@app.get("/api/metrics")
def list_metrics():
    """The goal metrics a client can be measured on."""
    return [{"key": key, **spec} for key, spec in GOAL_METRICS.items()]


# The stats the Analytics page compares period over period. Two cost stats,
# because an awareness ad set has no cost per result and a conversion ad set has
# no cost per 1,000 reached.
ANALYTICS_STATS = ("spend", "results", "cpa", "cost_per_1k_reach", "ctr")

# The result_action_type an awareness ad set carries: people, not an action.
REACH_ACTION = "reach"


def _cost_totals(conn, account_id: str, since: date | None, until: date | None) -> dict:
    """Spend split by what it bought, from the ad set rows. Cost per result
    covers conversion-goal ad sets only and cost per 1,000 reached awareness
    ones; mixing them would put a conversion price on plain delivery.
    """
    scope = [adset_daily_insights.c.account_id == account_id]
    if since is not None:
        scope.append(adset_daily_insights.c.date >= since)
    if until is not None:
        scope.append(adset_daily_insights.c.date <= until)

    # A NULL action type is an unmapped goal, and SQL's NULL comparison drops it
    # from both sides — which is right: it can price neither.
    conversion_spend, conversion_results = conn.execute(
        select(
            func.coalesce(func.sum(adset_daily_insights.c.spend), 0.0),
            func.sum(adset_daily_insights.c.results),
        ).where(*scope, adset_daily_insights.c.result_action_type != REACH_ACTION)
    ).one()
    reach_spend, reach_people = conn.execute(
        select(
            func.coalesce(func.sum(adset_daily_insights.c.spend), 0.0),
            func.sum(adset_daily_insights.c.reach),
        ).where(*scope, adset_daily_insights.c.result_action_type == REACH_ACTION)
    ).one()

    return {
        "cpa": round(conversion_spend / conversion_results, 2) if conversion_results else None,
        "cost_per_1k_reach": (
            round(reach_spend / reach_people * 1000, 2) if reach_people else None
        ),
        "conversion_spend": round(conversion_spend, 2),
        "awareness_spend": round(reach_spend, 2),
    }


def _period_totals(conn, account_id: str, since: date | None, until: date) -> dict:
    """One account's totals over [since, until]. Rates are None, not zero, when
    there is nothing to divide by."""
    scope = [daily_insights.c.account_id == account_id, daily_insights.c.date <= until]
    if since is not None:
        scope.append(daily_insights.c.date >= since)

    (
        spend,
        results,
        impressions,
        clicks,
        basis_low,
        basis_high,
        days_with_data,
    ) = conn.execute(
        select(
            func.coalesce(func.sum(daily_insights.c.spend), 0.0),
            func.sum(daily_insights.c.results),
            func.coalesce(func.sum(daily_insights.c.impressions), 0),
            func.coalesce(func.sum(daily_insights.c.clicks), 0),
            func.min(daily_insights.c.results_basis),
            func.max(daily_insights.c.results_basis),
            func.count(),
        ).where(*scope)
    ).one()

    totals = {
        "spend": round(spend, 2),
        "results": int(results) if results is not None else None,
        "results_basis": _basis(basis_low, basis_high),
        "impressions": int(impressions),
        "clicks": int(clicks),
        "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        "days_with_data": days_with_data,
    }
    totals.update(_cost_totals(conn, account_id, since, until))
    return totals


def _breakdown_row(entry: dict) -> dict:
    """One ad set's line, labelled by what it optimises for: an awareness ad set
    is priced per 1,000 people reached and never as a cost per result.
    """
    spend = round(entry["spend"], 2)
    goal = entry["optimization_goal"]
    action_type = entry["result_action_type"]

    if action_type == REACH_ACTION:
        cost = round(spend / entry["reach"] * 1000, 2) if entry["reach"] else None
        cost_label = "per 1,000 reached"
    elif action_type is None:
        cost = None
        cost_label = "goal not mapped"
    else:
        cost = round(spend / entry["results"], 2) if entry["results"] else None
        cost_label = "per result"

    return {
        "adset_id": entry["adset_id"],
        "adset_name": entry["adset_name"],
        "campaign_id": entry["campaign_id"],
        "campaign_name": entry["campaign_name"],
        "goal_label": goal.replace("_", " ").capitalize() if goal else "Unknown",
        "results": entry["results"] if action_type else None,
        "results_label": result_label(action_type),
        "spend": spend,
        "cost": cost,
        "cost_label": cost_label,
    }


def _change(current: float | None, previous: float | None) -> float | None:
    """Proportional change on the previous period. None when there is no
    earlier figure to compare against, rather than an infinite or 0% change."""
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous, 4)


KNOWN_IN_ERROR = 5


def _account_list(known: list[str]) -> str:
    """The known account ids, capped. An error message exists to orient someone,
    and a board with fifty clients should not recite all fifty."""
    shown = ", ".join(known[:KNOWN_IN_ERROR])
    extra = len(known) - KNOWN_IN_ERROR
    return f"{shown} and {extra} more" if extra > 0 else shown


@app.get("/api/analytics")
def analytics(account_id: str | None = None, days: int = 30):
    """One client's analytics over a window, with the equal-length period just
    before it for comparison. Read-only. `days=0` means all retained history,
    which has no earlier period to compare against.
    """
    if days < 0:
        raise HTTPException(status_code=422, detail="days must be 0 or greater")

    today = date.today()
    since = None if days == 0 else today - timedelta(days=days - 1)
    window = {
        "days": days,
        "since": str(since) if since else None,
        "until": str(today),
        "label": "all retained history" if days == 0 else f"the last {days} days",
    }

    with engine.connect() as conn:
        names = {
            row.account_id: row.client_name
            for row in conn.execute(
                select(account_targets.c.account_id, account_targets.c.client_name)
            )
        }
        known = sorted(
            set(conn.execute(select(daily_insights.c.account_id).distinct()).scalars().all())
            | set(names)
        )
        accounts = [{"account_id": a, "client_name": names.get(a) or a} for a in known]

        if not known:
            return {
                "window": window,
                "previous_window": None,
                "accounts": [],
                "account": None,
            }
        if account_id is None:
            account_id = known[0]
        elif account_id not in known:
            # Name the id that failed. The usual cause is a stale link — one
            # copied from another instance, or left in the URL by demo mode —
            # and a bare "Unknown account" gives nothing to compare against.
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Unknown account {account_id!r}. "
                    f"This board knows {_account_list(known)}."
                ),
            )

        current = _period_totals(conn, account_id, since, today)
        previous = previous_window = None
        if since is not None:
            previous_until = since - timedelta(days=1)
            previous_since = previous_until - timedelta(days=days - 1)
            previous = _period_totals(conn, account_id, previous_since, previous_until)
            previous_window = {"since": str(previous_since), "until": str(previous_until)}

        scope = [daily_insights.c.account_id == account_id]
        if since is not None:
            scope.append(daily_insights.c.date >= since)
        account_days = conn.execute(
            select(
                daily_insights.c.date,
                daily_insights.c.spend,
                daily_insights.c.results,
                daily_insights.c.results_basis,
                daily_insights.c.impressions,
                daily_insights.c.clicks,
                daily_insights.c.reach,
                daily_insights.c.frequency,
            )
            .where(*scope)
            .order_by(daily_insights.c.date)
        ).all()

        latest = conn.execute(
            select(func.max(daily_insights.c.date)).where(
                daily_insights.c.account_id == account_id
            )
        ).scalar()

        synced = bool(
            conn.execute(
                select(func.count())
                .select_from(adset_daily_insights)
                .where(adset_daily_insights.c.account_id == account_id)
            ).scalar()
        )
        adset_scope = [adset_daily_insights.c.account_id == account_id]
        if since is not None:
            adset_scope.append(adset_daily_insights.c.date >= since)
        adset_rows = conn.execute(
            select(adset_daily_insights)
            .where(*adset_scope)
            .order_by(adset_daily_insights.c.date)
        ).all()

    # Cost per day, split the same way as the period totals: only a conversion
    # ad set can price a result, only an awareness one can price reach.
    cost_by_day: dict[str, dict] = {}
    for row in adset_rows:
        day = cost_by_day.setdefault(
            str(row.date),
            {
                "conversion_spend": 0.0,
                "conversion_results": 0,
                "reported": [],
                "reach_spend": 0.0,
                "reach_people": 0,
            },
        )
        if row.result_action_type == REACH_ACTION:
            day["reach_spend"] += row.spend
            day["reach_people"] += row.reach or 0
        elif row.result_action_type is not None:
            day["conversion_spend"] += row.spend
            day["conversion_results"] += row.results or 0
            day["reported"].append(row.cost_per_result)

    daily = []
    for row in account_days:
        costs = cost_by_day.get(str(row.date), {})
        reported = costs.get("reported", [])
        # Meta's own cost per that action when one ad set delivered that day;
        # otherwise the day's conversion spend over its own results.
        if len(reported) == 1 and reported[0] is not None:
            cpa = reported[0]
        elif costs.get("conversion_results"):
            cpa = round(costs["conversion_spend"] / costs["conversion_results"], 2)
        else:
            cpa = None

        daily.append(
            {
                "date": str(row.date),
                "spend": round(row.spend, 2),
                "results": row.results,
                "results_basis": row.results_basis,
                "impressions": row.impressions,
                "clicks": row.clicks,
                "reach": row.reach,
                # Meta's own figure for the day. Null where reach is null, since
                # there is nothing to divide by — never zero, never averaged.
                "frequency": row.frequency,
                "cpa": cpa,
                "cost_per_1k_reach": (
                    round(costs["reach_spend"] / costs["reach_people"] * 1000, 2)
                    if costs.get("reach_people")
                    else None
                ),
                "ctr": round(row.clicks / row.impressions * 100, 2) if row.impressions else None,
            }
        )

    # Summed per ad set across the window. Rows arrive oldest first, so the
    # names and goal left standing are each ad set's most recent ones.
    by_adset: dict[str, dict] = {}
    for row in adset_rows:
        entry = by_adset.setdefault(
            row.adset_id,
            {"adset_id": row.adset_id, "spend": 0.0, "results": 0, "reach": 0},
        )
        entry["adset_name"] = row.adset_name or row.adset_id
        entry["campaign_id"] = row.campaign_id
        entry["campaign_name"] = row.campaign_name or row.campaign_id
        entry["optimization_goal"] = row.optimization_goal
        entry["result_action_type"] = row.result_action_type
        entry["spend"] += row.spend
        entry["results"] += row.results or 0
        entry["reach"] += row.reach or 0

    breakdown = sorted(
        (_breakdown_row(entry) for entry in by_adset.values() if entry["spend"] > 0),
        key=lambda entry: entry["spend"],
        reverse=True,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": window,
        "previous_window": previous_window,
        "accounts": accounts,
        "account": {
            "account_id": account_id,
            "client_name": names.get(account_id) or account_id,
            "last_data_date": str(latest) if latest else None,
        },
        # Which cost stats mean anything for this client in this window.
        "has_conversion_spend": current["conversion_spend"] > 0,
        "has_awareness_spend": current["awareness_spend"] > 0,
        "current": current,
        "previous": previous,
        "change": (
            {key: _change(current[key], previous[key]) for key in ANALYTICS_STATS}
            if previous
            else None
        ),
        "daily": daily,
        "breakdown": {"level": "adset", "synced": synced, "rows": breakdown},
    }


@app.put("/api/targets/{account_id}")
def set_target(account_id: str, payload: TargetIn):
    """Set a client's own goal. Writes to our store only — never to Meta."""
    if payload.goal_metric is not None and payload.goal_metric not in GOAL_METRICS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown goal metric. Choose one of: {', '.join(GOAL_METRICS)}",
        )
    upsert_account_target(
        engine,
        account_id=account_id,
        client_name=payload.client_name,
        goal_metric=payload.goal_metric,
        target_value=payload.target_value,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    return {"account_id": account_id, **payload.model_dump()}
