"""Nightly ingest: pull yesterday's insights for each configured ad account
and land them as normalized rows in Postgres (see ingest/db.py).

Also supports a one-off historical backfill:

    python -m ingest.run --days 90
    python -m ingest.run --since 2026-06-01 --until 2026-09-09

With no date arguments the behaviour is unchanged (yesterday only), so the
nightly job keeps working exactly as before.

Every run pulls the same window twice: once at account level, and once broken
down by ad set for the Analytics page's campaign / ad set breakdown.
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.adobjects.campaign import Campaign
from facebook_business.api import FacebookAdsApi

from ingest.db import (
    get_engine,
    init_db,
    prune_campaigns,
    set_daily_results,
    upsert_adset_daily_insight,
    upsert_campaign,
    upsert_daily_insight,
)
from ingest.results import daily_basis, resolve_results

INSIGHT_FIELDS = [
    AdsInsights.Field.date_start,
    AdsInsights.Field.spend,
    AdsInsights.Field.impressions,
    AdsInsights.Field.clicks,
    AdsInsights.Field.actions,
    # Reach is distinct from impressions (unique people, not total showings),
    # and action_values carries purchase revenue, which ROAS needs.
    AdsInsights.Field.reach,
    AdsInsights.Field.action_values,
    # Impressions per person, taken from Meta rather than worked out here: it is
    # impressions ÷ reach for the period requested, and reach is not additive,
    # so it cannot be rebuilt from stored daily figures afterwards.
    AdsInsights.Field.frequency,
]

# Ad-set level, for the Analytics breakdown. Each row names its campaign too,
# so campaign totals come from grouping these rather than from another pull.
ADSET_FIELDS = [
    AdsInsights.Field.date_start,
    AdsInsights.Field.campaign_id,
    AdsInsights.Field.campaign_name,
    AdsInsights.Field.adset_id,
    AdsInsights.Field.adset_name,
    AdsInsights.Field.spend,
    AdsInsights.Field.impressions,
    AdsInsights.Field.clicks,
    AdsInsights.Field.actions,
    # What a result actually costs, straight from Meta, plus the two figures
    # awareness and video goals are counted from (see ingest/results.py).
    AdsInsights.Field.cost_per_action_type,
    AdsInsights.Field.reach,
    AdsInsights.Field.video_thruplay_watched_actions,
]

# Action types that represent real purchase revenue, for ROAS.
PURCHASE_ACTION_TYPES = {
    "purchase",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
}


def load_account_ids() -> list[str]:
    raw = os.environ.get("META_AD_ACCOUNT_IDS", "")
    account_ids = [a.strip() for a in raw.split(",") if a.strip()]
    if not account_ids:
        sys.exit("META_AD_ACCOUNT_IDS is not set (comma-separated act_<id> values)")
    return account_ids


def total_conversions(actions: list[dict] | None) -> int:
    """Every action type added together. Kept only to keep filling the legacy
    `conversions` column: it counts unrelated outcomes as one figure, so the
    app reads `results` instead (ingest/results.py).
    """
    if not actions:
        return 0
    return sum(int(a["value"]) for a in actions)


def load_adset_goals(account_id: str) -> dict[str, dict]:
    """Each ad set's optimisation goal, which decides what counts as a result.
    The goal lives on the ad set itself, never on its insights.
    """
    goals = {}
    for adset in AdAccount(account_id).get_ad_sets(
        fields=[AdSet.Field.id, AdSet.Field.optimization_goal, AdSet.Field.promoted_object],
        params={"limit": 500},
    ):
        promoted = adset.get("promoted_object") or {}
        goals[adset["id"]] = {
            "optimization_goal": adset.get("optimization_goal"),
            # Pixel conversions name their event here, e.g. PURCHASE.
            "custom_event_type": promoted.get("custom_event_type"),
        }
    return goals


def purchase_value(action_values: list[dict] | None) -> float | None:
    """Revenue attributed to purchases. None (not zero) when Meta returned no
    action values at all, so 'no purchase data' stays distinct from 'no sales'.
    """
    if not action_values:
        return None
    return sum(
        float(a.get("value", 0))
        for a in action_values
        if a.get("action_type") in PURCHASE_ACTION_TYPES
    )


def build_params(since: date | None, until: date | None, level: str = "account") -> dict:
    """Yesterday-only by default; a daily-broken-down range when backfilling.

    time_increment=1 makes Meta return one row per day for the whole range in
    a single call, rather than us issuing one request per day.
    """
    if since is None:
        return {"date_preset": "yesterday", "level": level}
    return {
        "time_range": {"since": since.isoformat(), "until": until.isoformat()},
        "time_increment": 1,
        "level": level,
    }


def pull_account(
    account_id: str, engine, since: date | None = None, until: date | None = None
) -> int:
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=INSIGHT_FIELDS,
        params=build_params(since, until),
    )
    if not insights:
        window = "yesterday" if since is None else f"{since}..{until}"
        print(f"{account_id}: no rows for {window}")
        return 0

    stored = 0
    for row in insights:
        insight_date = datetime.strptime(row["date_start"], "%Y-%m-%d").date()
        spend = float(row.get("spend", 0))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        conversions = total_conversions(row.get("actions"))
        reach = int(row["reach"]) if row.get("reach") is not None else None
        revenue = purchase_value(row.get("action_values"))
        frequency = float(row["frequency"]) if row.get("frequency") is not None else None

        upsert_daily_insight(
            engine,
            account_id=account_id,
            insight_date=insight_date,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            reach=reach,
            purchase_value=revenue,
            frequency=frequency,
        )
        stored += 1
        print(
            f"{account_id}: {insight_date} spend=${spend} "
            f"impressions={impressions} clicks={clicks} conversions={conversions} "
            f"reach={reach if reach is not None else '-'} "
            f"frequency={frequency if frequency is not None else '-'} "
            f"revenue={revenue if revenue is not None else '-'} (stored)"
        )

    return stored


def pull_adsets(
    account_id: str,
    engine,
    goals: dict[str, dict],
    since: date | None = None,
    until: date | None = None,
) -> tuple[int, dict[date, tuple[int | None, str | None]]]:
    """The same window broken down by ad set, each row's results counted as its
    own optimisation goal defines them.

    Returns the row count and, per day, the account's summed results and what
    those results are — which the caller writes onto the account-level row.
    """
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=ADSET_FIELDS,
        params=build_params(since, until, level="adset"),
    )

    stored = 0
    per_day: dict[date, dict] = {}
    for row in insights:
        insight_date = datetime.strptime(row["date_start"], "%Y-%m-%d").date()
        adset_id = row["adset_id"]
        goal = goals.get(adset_id, {})
        spend = float(row.get("spend", 0))
        reach = int(row["reach"]) if row.get("reach") is not None else None

        results, basis, action_type, cost = resolve_results(
            goal=goal.get("optimization_goal"),
            custom_event_type=goal.get("custom_event_type"),
            actions=row.get("actions"),
            thruplay_actions=row.get("video_thruplay_watched_actions"),
            cost_per_action_type=row.get("cost_per_action_type"),
            reach=reach,
            spend=spend,
        )

        upsert_adset_daily_insight(
            engine,
            account_id=account_id,
            adset_id=adset_id,
            insight_date=insight_date,
            adset_name=row.get("adset_name"),
            campaign_id=row["campaign_id"],
            campaign_name=row.get("campaign_name"),
            spend=spend,
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            conversions=total_conversions(row.get("actions")),
            reach=reach,
            optimization_goal=goal.get("optimization_goal"),
            result_action_type=action_type,
            results=results,
            cost_per_result=cost,
        )
        stored += 1

        day = per_day.setdefault(insight_date, {"results": None, "bases": []})
        day["bases"].append(basis)
        if results is not None:
            day["results"] = (day["results"] or 0) + results

    window = "yesterday" if since is None else f"{since}..{until}"
    print(f"{account_id}: {stored} ad set row(s) stored for {window}")

    return stored, {
        day: (values["results"], daily_basis(values["bases"]))
        for day, values in per_day.items()
    }


def parse_meta_time(raw: str | None) -> datetime | None:
    """Meta's campaign timestamps, e.g. 2026-09-12T08:17:20+0100."""
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")


def pull_campaigns(account_id: str, engine) -> tuple[int, int]:
    """Every campaign's current state, for the board's active count.

    `effective_status` rather than `status`, because only the effective one
    accounts for a pause above the campaign; and the account's own status on
    top of that, because a campaign on a closed account still reads ACTIVE
    while nothing it contains can deliver.
    """
    account = AdAccount(account_id)
    account_status = account.api_get(fields=[AdAccount.Field.account_status]).get(
        "account_status"
    )
    account_active = account_status == 1  # 1 is ACTIVE; every other code is not.

    seen: set[str] = set()
    active = 0
    for campaign in account.get_campaigns(
        fields=[
            Campaign.Field.id,
            Campaign.Field.name,
            Campaign.Field.effective_status,
            # The schedule a goal's pace is judged against.
            Campaign.Field.start_time,
            Campaign.Field.stop_time,
        ],
        params={"limit": 500},
    ):
        effective_status = campaign.get("effective_status")
        upsert_campaign(
            engine,
            account_id=account_id,
            campaign_id=campaign["id"],
            name=campaign.get("name"),
            effective_status=effective_status,
            account_active=account_active,
            start_time=parse_meta_time(campaign.get("start_time")),
            stop_time=parse_meta_time(campaign.get("stop_time")),
        )
        seen.add(campaign["id"])
        if account_active and effective_status == "ACTIVE":
            active += 1

    removed = prune_campaigns(engine, account_id, seen)
    note = "" if account_active else f", account_status={account_status} (not active)"
    print(
        f"{account_id}: {len(seen)} campaign(s), {active} active"
        f"{f', {removed} removed' if removed else ''}{note}"
    )
    return len(seen), active


def parse_args(argv: list[str] | None = None) -> tuple[date | None, date | None]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        help="Backfill the last N days, ending yesterday.",
    )
    parser.add_argument("--since", type=date.fromisoformat, help="Backfill from this date (YYYY-MM-DD).")
    parser.add_argument("--until", type=date.fromisoformat, help="Backfill up to this date (defaults to yesterday).")
    args = parser.parse_args(argv)

    if args.days and args.since:
        parser.error("use either --days or --since/--until, not both")

    yesterday = date.today() - timedelta(days=1)

    if args.days:
        if args.days < 1:
            parser.error("--days must be at least 1")
        until = args.until or yesterday
        return until - timedelta(days=args.days - 1), until

    if args.since:
        until = args.until or yesterday
        if args.since > until:
            parser.error("--since must not be after --until")
        return args.since, until

    if args.until:
        parser.error("--until requires --days or --since")

    return None, None


def main() -> None:
    since, until = parse_args()

    load_dotenv()
    access_token = os.environ.get("META_ACCESS_TOKEN")
    if not access_token:
        sys.exit("META_ACCESS_TOKEN is not set")

    FacebookAdsApi.init(
        app_id=os.environ.get("META_APP_ID"),
        app_secret=os.environ.get("META_APP_SECRET"),
        access_token=access_token,
    )

    engine = get_engine()
    init_db(engine)

    total = 0
    adset_total = 0
    for account_id in load_account_ids():
        pull_campaigns(account_id, engine)
        goals = load_adset_goals(account_id)
        total += pull_account(account_id, engine, since, until)
        stored, per_day = pull_adsets(account_id, engine, goals, since, until)
        adset_total += stored

        # The account row's own actions array mixes every ad set's outcome
        # together, so its results come from the ad sets instead.
        for insight_date, (results, basis) in sorted(per_day.items()):
            set_daily_results(engine, account_id, insight_date, results, basis)
            print(f"{account_id}: {insight_date} results={results} ({basis})")

    window = "yesterday" if since is None else f"{since}..{until}"
    print(f"\nDone: {total} account row(s) and {adset_total} ad set row(s) stored for {window}.")


if __name__ == "__main__":
    main()
