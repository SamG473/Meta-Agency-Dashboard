"""FastAPI backend. Reads only from Postgres — never calls Meta directly
(see CLAUDE.md architecture rules).
"""
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

load_dotenv()
app = FastAPI(title="Meta Agency Dashboard")
engine = get_engine()

# The dashboard is served from a separate dev server in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# The metrics a client can be measured on. `direction` says which way is good,
# which the UI needs in order to colour the correct end of the progress bar:
# missing a leads target is a shortfall, missing a cost target is an overspend.
# Alert-only throughout — breaching a target notifies, it never touches a
# campaign (CLAUDE.md).
GOAL_METRICS = {
    "leads": {"label": "Leads", "unit": "count", "direction": "higher"},
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
        # Daily reach summed over the window. Meta deduplicates people within a
        # day but not across days, so this over-counts unique reach.
        "note": "summed daily reach, not deduplicated across days",
    },
}

DEFAULT_GOAL_METRIC = "cost_per_result"


def _ctr(clicks: int, impressions: int) -> float:
    return round(clicks / impressions * 100, 2) if impressions else 0.0


class TargetIn(BaseModel):
    client_name: str | None = Field(default=None, max_length=200)
    goal_metric: str | None = Field(default=None)
    target_value: float | None = Field(default=None, gt=0)


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


def _evaluate(metric: str | None, target: float | None, actual: float | None):
    """Standing against this client's OWN target. Returns (state, deviation),
    where deviation is signed so that positive always means worse, whichever
    direction the metric runs.
    """
    if metric is None or target is None:
        return "no_target", None
    if actual is None:
        return "no_data", None

    direction = GOAL_METRICS.get(metric, {}).get("direction", "lower")
    deviation = (
        (actual - target) / target if direction == "lower" else (target - actual) / target
    )
    state = "behind" if deviation > 0 else "on_track"
    return state, round(deviation, 4)


# States that put an account on the board's attention count.
ATTENTION_STATES = {"behind", "no_data"}


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
            state, deviation = _evaluate(metric, target, actual)
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
        total_spend, total_results, total_low, total_high = conn.execute(
            select(
                func.coalesce(func.sum(daily_insights.c.spend), 0.0),
                func.sum(daily_insights.c.results),
                func.min(daily_insights.c.results_basis),
                func.max(daily_insights.c.results_basis),
            ).where(*totals_scope)
        ).one()
        latest_overall = conn.execute(select(func.max(daily_insights.c.date))).scalar()

        # Live campaign state, not a windowed figure. None rather than zero
        # when no campaign has ever been synced: unknown is not "none active".
        campaigns_known = conn.execute(select(func.count()).select_from(campaigns)).scalar()
        active_campaigns = (
            conn.execute(
                select(func.count())
                .select_from(campaigns)
                .where(
                    campaigns.c.effective_status == "ACTIVE",
                    campaigns.c.account_active.is_(True),
                )
            ).scalar()
            if campaigns_known
            else None
        )

        # Retained history across the whole portfolio, deliberately independent
        # of the selected window: this is the record Meta's own interface
        # discards, and the board should always be able to show it.
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
                .group_by(daily_insights.c.date)
                .order_by(daily_insights.c.date)
            ).all()
        ]

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
        "accounts": accounts,
    }


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
            raise HTTPException(status_code=404, detail="Unknown account")

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
    )
    return {"account_id": account_id, **payload.model_dump()}
