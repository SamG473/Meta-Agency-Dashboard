"""FastAPI backend. Reads only from Postgres — never calls Meta directly
(see CLAUDE.md architecture rules).
"""
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ingest.db import account_targets, daily_insights, get_engine, upsert_account_target

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


def _cpr(spend: float, conversions: int) -> float:
    return round(spend / conversions, 2) if conversions else 0.0


class TargetIn(BaseModel):
    client_name: str | None = Field(default=None, max_length=200)
    goal_metric: str | None = Field(default=None)
    target_value: float | None = Field(default=None, gt=0)


def _metric_actual(metric: str, spend: float, conversions: int, reach: int | None,
                   revenue: float | None) -> float | None:
    """This client's goal metric over the window, or None when the underlying
    data was never ingested — which must stay distinct from a value of zero.
    """
    if metric in ("cost_per_result", "cost_per_lead"):
        return round(spend / conversions, 2) if conversions else None
    if metric == "leads":
        return float(conversions)
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
        row.conversions,
        row.reach,
        row.purchase_value,
    )


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

            spend, impressions, clicks, conversions, reach, revenue = conn.execute(
                select(
                    func.coalesce(func.sum(daily_insights.c.spend), 0.0),
                    func.coalesce(func.sum(daily_insights.c.impressions), 0),
                    func.coalesce(func.sum(daily_insights.c.clicks), 0),
                    func.coalesce(func.sum(daily_insights.c.conversions), 0),
                    func.sum(daily_insights.c.reach),
                    func.sum(daily_insights.c.purchase_value),
                ).where(*scoped)
            ).one()

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
                    daily_insights.c.conversions,
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
                    "conversions": row.conversions,
                }
                for row in trend_rows
            ]

            actual = _metric_actual(metric, spend, conversions, reach, revenue)
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
                "conversions": conversions,
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
        total_spend, total_conversions = conn.execute(
            select(
                func.coalesce(func.sum(daily_insights.c.spend), 0.0),
                func.coalesce(func.sum(daily_insights.c.conversions), 0),
            ).where(*totals_scope)
        ).one()
        latest_overall = conn.execute(select(func.max(daily_insights.c.date))).scalar()

        # Retained history across the whole portfolio, deliberately independent
        # of the selected window: this is the record Meta's own interface
        # discards, and the board should always be able to show it.
        portfolio_history = [
            {
                "date": str(row.date),
                "spend": round(row.spend, 2),
                "conversions": row.conversions,
                "accounts": row.accounts,
            }
            for row in conn.execute(
                select(
                    daily_insights.c.date,
                    func.sum(daily_insights.c.spend).label("spend"),
                    func.sum(daily_insights.c.conversions).label("conversions"),
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
            "accounts_tracked": len(accounts),
            "accounts_needing_attention": len(needing),
            "accounts_behind": sum(1 for a in accounts if a["state"] == "behind"),
            "accounts_untargeted": sum(
                1 for a in accounts if a["target_value"] is None
            ),
            "spend": round(total_spend, 2),
            "conversions": total_conversions,
            "cpr": _cpr(total_spend, total_conversions) if total_conversions else None,
            "last_data_date": str(latest_overall) if latest_overall else None,
        },
        "portfolio_history": portfolio_history,
        "accounts": accounts,
    }


@app.get("/api/metrics")
def list_metrics():
    """The goal metrics a client can be measured on."""
    return [{"key": key, **spec} for key, spec in GOAL_METRICS.items()]


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
