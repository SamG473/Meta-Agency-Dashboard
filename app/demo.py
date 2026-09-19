"""Demo mode: a fictional agency portfolio, served instead of the real store.

Switched on with DEMO_MODE=true. The switch is one line in app/main.py — the
engine the API talks to — so no route carries a demo branch and the real
database is never opened: nothing in this module reads DATABASE_URL, and the
ingest never runs in this mode.

Everything is generated from a fixed seed, so a deployed demo looks identical on
every load and in every screenshot. The portfolio deliberately exercises what
the board was built for: mixed optimisation goals, so the goal-aware results
logic shows; targets paced to land on different states, so the badges are not
all green; and one client with a gap in delivery, so the charts' gap handling is
visible.

Every name here is invented. No figure comes from a real ad account.
"""
import os
import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from ingest.db import (
    account_targets,
    adset_daily_insights,
    campaigns,
    daily_insights,
    metadata,
)

SEED = 20260918
HISTORY_DAYS = 60

TRUE_VALUES = {"1", "true", "yes", "on"}
DEMO_MODE = os.environ.get("DEMO_MODE", "").strip().lower() in TRUE_VALUES


# Each client: how its ad set is optimised, what it is judged on, and which
# state its target should land in. Targets are solved backwards from the
# generated delivery so the states are reliable rather than hopeful.
CLIENTS = [
    {
        "account_id": "act_demo_1001",
        "client_name": "Harbour & Vine",
        "campaign": "Harbour & Vine — Reach — IG",
        "adset": "Coastal towns 25-54",
        "goal": "REACH",
        "metric": "reach",
        "state": "on_track",
        "spend_base": 88.0,
        "spend_trend": 0.25,
        "cpm": 5.40,
        "ctr": 0.009,
        "freq": (1.15, 2.30),
        "period": (-24, 12),
    },
    {
        "account_id": "act_demo_1002",
        "client_name": "Peakline Fitness",
        "campaign": "Peakline — Lead gen — Q3",
        "adset": "Trial pass — 5 mile radius",
        "goal": "LEAD_GENERATION",
        "metric": "leads",
        "state": "at_risk",
        "spend_base": 64.0,
        "spend_trend": -0.1,
        "cpm": 8.10,
        "ctr": 0.016,
        "freq": (1.30, 2.60),
        "lead_rate": 0.085,
        "period": (-28, 9),
    },
    {
        "account_id": "act_demo_1003",
        "client_name": "Aurelia Skincare",
        "campaign": "Aurelia — Purchases — Autumn",
        "adset": "Retargeting — 30 day viewers",
        "goal": "OFFSITE_CONVERSIONS",
        "custom_event_type": "PURCHASE",
        "metric": "roas",
        "state": "on_track",
        "spend_base": 142.0,
        "spend_trend": 0.35,
        "cpm": 11.20,
        "ctr": 0.019,
        "freq": (1.40, 2.90),
        "purchase_rate": 0.035,
        "order_value": 46.0,
        "period": (-30, 14),
    },
    {
        "account_id": "act_demo_1004",
        "client_name": "Copper & Clay",
        "campaign": "Copper & Clay — Workshops — Lead gen",
        "adset": "Makers & hobbyists",
        "goal": "LEAD_GENERATION",
        "metric": "leads",
        "state": "behind",
        "spend_base": 37.0,
        "spend_trend": -0.2,
        "cpm": 6.80,
        "ctr": 0.011,
        "freq": (1.10, 1.95),
        "lead_rate": 0.055,
        "period": (-26, 11),
        # Ten days dark mid-flight: the client paused. Wide on purpose — the
        # charts join gaps of a week or less, so a shorter pause would be
        # drawn straight through and demonstrate nothing.
        "gap": (28, 37),
    },
    {
        "account_id": "act_demo_1005",
        "client_name": "Northgate Motors",
        "campaign": "Northgate — Test drives — Always on",
        "adset": "In-market, 20 mile radius",
        "goal": "LEAD_GENERATION",
        "metric": "cost_per_lead",
        "state": "behind",
        "spend_base": 176.0,
        "spend_trend": 0.15,
        "cpm": 9.60,
        "ctr": 0.013,
        "freq": (1.25, 2.75),
        "lead_rate": 0.042,
        "period": (-22, 16),
    },
    {
        "account_id": "act_demo_1006",
        "client_name": "Sable Interiors",
        "campaign": "Sable — Showroom launch — Reach",
        "adset": "Design-led homeowners",
        "goal": "REACH",
        "metric": "reach",
        "state": "met",
        "spend_base": 119.0,
        "spend_trend": -0.35,
        "cpm": 4.70,
        "ctr": 0.007,
        "freq": (1.20, 2.10),
        # A finished flight: the period ended a week ago, so this one reads MET.
        "period": (-47, -7),
    },
]

# How far off the pace each state sits. Pace ratio is actual ÷ what should have
# been delivered by now, and the board's own thresholds are 1.0 and 0.85.
PACE_FOR_STATE = {"on_track": 1.22, "at_risk": 0.92, "behind": 0.64}


def _reach_action(goal):
    return goal == "REACH"


def _result_action_type(client):
    if client["goal"] == "REACH":
        return "reach"
    if client["goal"] == "LEAD_GENERATION":
        return "onsite_conversion.lead_grouped"
    return f"offsite_conversion.fb_pixel_{client['custom_event_type'].lower()}"


def _daily_rows(client, rng, today):
    """One row per delivering day, with plausible agency-scale figures.

    Frequency rises gently across the flight, and impressions follow from spend
    and CPM, so reach, frequency and impressions stay consistent with each other
    rather than being three independent random numbers.
    """
    rows = []
    first_day = today - timedelta(days=HISTORY_DAYS - 1)

    for offset in range(HISTORY_DAYS):
        gap = client.get("gap")
        if gap and gap[0] <= offset <= gap[1]:
            continue  # dark days: no row at all, exactly as a pause looks

        day = first_day + timedelta(days=offset)
        progress = offset / (HISTORY_DAYS - 1)
        weekend = 0.78 if day.weekday() >= 5 else 1.0

        spend = round(
            client["spend_base"]
            * (1 + client["spend_trend"] * progress)
            * weekend
            * rng.uniform(0.88, 1.12),
            2,
        )
        cpm = client["cpm"] * rng.uniform(0.92, 1.09)
        impressions = max(1, int(spend / cpm * 1000))

        low, high = client["freq"]
        frequency = max(1.0, low + (high - low) * progress + rng.uniform(-0.05, 0.05))
        reach = max(1, int(impressions / frequency))
        # Store what the division actually gives, so the chart and the figures agree.
        frequency = round(impressions / reach, 6)

        clicks = max(0, int(impressions * client["ctr"] * rng.uniform(0.82, 1.18)))

        if _reach_action(client["goal"]):
            results = reach
            cost_per_result = round(spend / reach * 1000, 2)
            revenue = None
        elif client["goal"] == "LEAD_GENERATION":
            results = max(0, int(clicks * client["lead_rate"] * rng.uniform(0.7, 1.3)))
            cost_per_result = round(spend / results, 2) if results else None
            revenue = None
        else:
            results = max(0, int(clicks * client["purchase_rate"] * rng.uniform(0.6, 1.4)))
            cost_per_result = round(spend / results, 2) if results else None
            revenue = round(results * client["order_value"] * rng.uniform(0.85, 1.2), 2)

        rows.append(
            {
                "date": day,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "reach": reach,
                "frequency": frequency,
                "results": results,
                "cost_per_result": cost_per_result,
                "purchase_value": revenue,
                # The legacy all-actions figure the app no longer reads: still
                # inflated here, because that is what Meta really returns.
                "conversions": results + clicks + int(impressions * 0.012),
            }
        )

    return rows


def _target_value(client, rows, period_start, period_end, today):
    """A target that lands this client on its intended state.

    Solved from the delivery just generated: for a paced goal, from what should
    have been delivered by the elapsed share of the period; for a rate goal,
    from the rate actually achieved.
    """
    # The same slice the board judges on: the period, up to today if it is still
    # running. Solving against a wider slice would hand a finished client a
    # target it never actually reached.
    in_period = [r for r in rows if period_start <= r["date"] <= min(today, period_end)]

    if client["metric"] in ("reach", "leads"):
        actual = sum(r["results"] for r in in_period)
        if client["state"] == "met":
            return round(actual * 0.88)  # finished, and comfortably over
        total_days = (period_end - period_start).days + 1
        elapsed = min(max((today - period_start).days + 1, 0), total_days)
        fraction = elapsed / total_days
        pace = PACE_FOR_STATE[client["state"]]
        return round(actual / (pace * fraction))

    spend = sum(r["spend"] for r in in_period)
    results = sum(r["results"] for r in in_period)

    if client["metric"] == "roas":
        revenue = sum(r["purchase_value"] or 0 for r in in_period)
        achieved = revenue / spend if spend else 0
        return round(achieved * (0.82 if client["state"] == "on_track" else 1.25), 2)

    achieved = spend / results if results else 0  # cost per lead
    return round(achieved * (1.18 if client["state"] == "on_track" else 0.78), 2)


def _seed(engine, today):
    rng = random.Random(SEED)

    for client in CLIENTS:
        rows = _daily_rows(client, rng, today)
        period_start = today + timedelta(days=client["period"][0])
        period_end = today + timedelta(days=client["period"][1])
        action_type = _result_action_type(client)
        basis = "reach" if _reach_action(client["goal"]) else "action"
        campaign_id = f"{client['account_id']}_c1"
        adset_id = f"{client['account_id']}_a1"

        with engine.begin() as conn:
            conn.execute(
                account_targets.insert().values(
                    account_id=client["account_id"],
                    client_name=client["client_name"],
                    goal_metric=client["metric"],
                    target_value=_target_value(client, rows, period_start, period_end, today),
                    period_start=period_start,
                    period_end=period_end,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            conn.execute(
                campaigns.insert().values(
                    account_id=client["account_id"],
                    campaign_id=campaign_id,
                    name=client["campaign"],
                    effective_status="ACTIVE",
                    account_active=True,
                    start_time=datetime.combine(period_start, time(9, 0), timezone.utc),
                    stop_time=datetime.combine(period_end, time(23, 0), timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            conn.execute(
                daily_insights.insert(),
                [
                    {
                        "account_id": client["account_id"],
                        "date": row["date"],
                        "spend": row["spend"],
                        "impressions": row["impressions"],
                        "clicks": row["clicks"],
                        "conversions": row["conversions"],
                        "reach": row["reach"],
                        "purchase_value": row["purchase_value"],
                        "frequency": row["frequency"],
                        "results": row["results"],
                        "results_basis": basis,
                    }
                    for row in rows
                ],
            )
            conn.execute(
                adset_daily_insights.insert(),
                [
                    {
                        "account_id": client["account_id"],
                        "adset_id": adset_id,
                        "date": row["date"],
                        "adset_name": client["adset"],
                        "campaign_id": campaign_id,
                        "campaign_name": client["campaign"],
                        "spend": row["spend"],
                        "impressions": row["impressions"],
                        "clicks": row["clicks"],
                        "conversions": row["conversions"],
                        "reach": row["reach"],
                        "optimization_goal": client["goal"],
                        "result_action_type": action_type,
                        "results": row["results"],
                        "cost_per_result": row["cost_per_result"],
                    }
                    for row in rows
                ],
            )


def build_demo_engine():
    """An in-memory database holding the fictional portfolio.

    StaticPool keeps every connection on the same in-memory database, which
    SQLite would otherwise give one per connection.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    _seed(engine, date.today())
    return engine
