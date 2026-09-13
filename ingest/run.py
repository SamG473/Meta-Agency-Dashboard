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
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.api import FacebookAdsApi

from ingest.db import get_engine, init_db, upsert_adset_daily_insight, upsert_daily_insight

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
    if not actions:
        return 0
    return sum(int(a["value"]) for a in actions)


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
        )
        stored += 1
        print(
            f"{account_id}: {insight_date} spend=${spend} "
            f"impressions={impressions} clicks={clicks} conversions={conversions} "
            f"reach={reach if reach is not None else '-'} "
            f"revenue={revenue if revenue is not None else '-'} (stored)"
        )

    return stored


def pull_adsets(
    account_id: str, engine, since: date | None = None, until: date | None = None
) -> int:
    """The same window broken down by ad set. Results are counted with the same
    total_conversions as the account row, so the breakdown and the account
    totals measure results the same way (inflated included — see CLAUDE.md).
    """
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=ADSET_FIELDS,
        params=build_params(since, until, level="adset"),
    )

    stored = 0
    for row in insights:
        upsert_adset_daily_insight(
            engine,
            account_id=account_id,
            adset_id=row["adset_id"],
            insight_date=datetime.strptime(row["date_start"], "%Y-%m-%d").date(),
            adset_name=row.get("adset_name"),
            campaign_id=row["campaign_id"],
            campaign_name=row.get("campaign_name"),
            spend=float(row.get("spend", 0)),
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            conversions=total_conversions(row.get("actions")),
        )
        stored += 1

    window = "yesterday" if since is None else f"{since}..{until}"
    print(f"{account_id}: {stored} ad set row(s) stored for {window}")
    return stored


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
        total += pull_account(account_id, engine, since, until)
        adset_total += pull_adsets(account_id, engine, since, until)

    window = "yesterday" if since is None else f"{since}..{until}"
    print(f"\nDone: {total} account row(s) and {adset_total} ad set row(s) stored for {window}.")


if __name__ == "__main__":
    main()
