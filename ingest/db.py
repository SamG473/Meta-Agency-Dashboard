"""Normalized storage for pulled Meta insights.

Defaults to a local SQLite file so early dev isn't blocked on a Supabase
signup (CLAUDE.md allows this). Set DATABASE_URL to a Postgres URL to point
at Supabase instead — no query changes needed either way.
"""
import os
from datetime import date

from sqlalchemy import Column, Date, Float, Integer, MetaData, String, Table, create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

metadata = MetaData()

daily_insights = Table(
    "daily_insights",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("spend", Float, nullable=False),
    Column("impressions", Integer, nullable=False),
    Column("clicks", Integer, nullable=False),
    Column("conversions", Integer, nullable=False),
)


def get_engine() -> Engine:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///dashboard.db")
    return create_engine(database_url)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)


def upsert_daily_insight(
    engine: Engine,
    account_id: str,
    insight_date: date,
    spend: float,
    impressions: int,
    clicks: int,
    conversions: int,
) -> None:
    values = {
        "account_id": account_id,
        "date": insight_date,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
    }
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(daily_insights).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id", "date"],
        set_={
            "spend": stmt.excluded.spend,
            "impressions": stmt.excluded.impressions,
            "clicks": stmt.excluded.clicks,
            "conversions": stmt.excluded.conversions,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
