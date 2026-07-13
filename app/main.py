"""FastAPI backend. Reads only from Postgres — never calls Meta directly
(see CLAUDE.md architecture rules).
"""
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy import func, select

from ingest.db import daily_insights, get_engine

load_dotenv()
app = FastAPI()
engine = get_engine()


def _ctr(clicks: int, impressions: int) -> float:
    return round(clicks / impressions * 100, 2) if impressions else 0.0


def _cpr(spend: float, conversions: int) -> float:
    return round(spend / conversions, 2) if conversions else 0.0


@app.get("/accounts")
def list_accounts():
    with engine.connect() as conn:
        account_ids = conn.execute(
            select(daily_insights.c.account_id).distinct()
        ).scalars().all()

        accounts = []
        for account_id in account_ids:
            totals = conn.execute(
                select(
                    func.sum(daily_insights.c.spend),
                    func.sum(daily_insights.c.impressions),
                    func.sum(daily_insights.c.clicks),
                    func.sum(daily_insights.c.conversions),
                ).where(daily_insights.c.account_id == account_id)
            ).one()
            spend, impressions, clicks, conversions = totals

            trend_rows = conn.execute(
                select(
                    daily_insights.c.date,
                    daily_insights.c.spend,
                    daily_insights.c.conversions,
                )
                .where(daily_insights.c.account_id == account_id)
                .order_by(daily_insights.c.date)
            ).all()

            accounts.append({
                "account_id": account_id,
                "spend": round(spend, 2),
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "ctr": _ctr(clicks, impressions),
                "cpr": _cpr(spend, conversions),
                "trend": [
                    {"date": str(row.date), "spend": row.spend, "conversions": row.conversions}
                    for row in trend_rows
                ],
            })

    return accounts


@app.get("/portfolio")
def portfolio_rollup():
    month_start = date.today().replace(day=1)
    with engine.connect() as conn:
        spend, conversions, account_count = conn.execute(
            select(
                func.coalesce(func.sum(daily_insights.c.spend), 0),
                func.coalesce(func.sum(daily_insights.c.conversions), 0),
                func.count(func.distinct(daily_insights.c.account_id)),
            ).where(daily_insights.c.date >= month_start)
        ).one()

    return {
        "spend_this_month": round(spend, 2),
        "conversions_this_month": conversions,
        "account_count": account_count,
    }
