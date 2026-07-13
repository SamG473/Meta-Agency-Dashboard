"""Nightly ingest: pull yesterday's insights for each configured ad account
and land them as normalized rows in Postgres (see ingest/db.py).
"""
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.api import FacebookAdsApi

from ingest.db import get_engine, init_db, upsert_daily_insight

INSIGHT_FIELDS = [
    AdsInsights.Field.date_start,
    AdsInsights.Field.spend,
    AdsInsights.Field.impressions,
    AdsInsights.Field.clicks,
    AdsInsights.Field.actions,
]


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


def pull_account(account_id: str, engine) -> None:
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=INSIGHT_FIELDS,
        params={"date_preset": "yesterday", "level": "account"},
    )
    if not insights:
        print(f"{account_id}: no rows for yesterday")
        return
    row = insights[0]
    insight_date = datetime.strptime(row["date_start"], "%Y-%m-%d").date()
    spend = float(row.get("spend", 0))
    impressions = int(row.get("impressions", 0))
    clicks = int(row.get("clicks", 0))
    conversions = total_conversions(row.get("actions"))

    upsert_daily_insight(
        engine,
        account_id=account_id,
        insight_date=insight_date,
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
    )
    print(
        f"{account_id}: {insight_date} spend=${spend} "
        f"impressions={impressions} clicks={clicks} conversions={conversions} "
        f"(stored)"
    )


def main() -> None:
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

    for account_id in load_account_ids():
        pull_account(account_id, engine)


if __name__ == "__main__":
    main()
