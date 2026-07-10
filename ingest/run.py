"""Week 1 de-risk script (see SPEC.md).

Pulls yesterday's spend/impressions/clicks/conversions for the configured ad
accounts and prints them. Proves the Meta auth + Marketing API path works
before anything is built on top of it. Does not write to a database yet —
Postgres landing is a later milestone.
"""
import os
import sys

from dotenv import load_dotenv
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
from facebook_business.api import FacebookAdsApi

INSIGHT_FIELDS = [
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


def pull_account(account_id: str) -> None:
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=INSIGHT_FIELDS,
        params={"date_preset": "yesterday", "level": "account"},
    )
    if not insights:
        print(f"{account_id}: no rows for yesterday")
        return
    row = insights[0]
    print(
        f"{account_id}: spend=${row.get('spend', '0')} "
        f"impressions={row.get('impressions', '0')} "
        f"clicks={row.get('clicks', '0')} "
        f"conversions={total_conversions(row.get('actions'))}"
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

    for account_id in load_account_ids():
        pull_account(account_id)


if __name__ == "__main__":
    main()
