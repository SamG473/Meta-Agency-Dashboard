"""Normalized storage for pulled Meta insights.

Defaults to a local SQLite file so early dev isn't blocked on a Supabase
signup (CLAUDE.md allows this). Set DATABASE_URL to a Postgres URL to point
at Supabase instead — no query changes needed either way.
"""
import os
from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    text,
)
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
    # Nullable because rows ingested before these fields were pulled have no
    # value for them, and a zero would be a lie rather than a gap.
    Column("reach", Integer, nullable=True),
    Column("purchase_value", Float, nullable=True),
)

# Per-client goals. Each account is judged against its own target and never
# against another account's — see SPEC.md on aggregation vs comparison.
# `goal_metric` names which metric this client is measured on; the metric's
# unit and direction live in the API's registry, not here.
account_targets = Table(
    "account_targets",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("client_name", String, nullable=True),
    Column("goal_metric", String, nullable=True),
    Column("target_value", Float, nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# Ad-set detail for the Analytics breakdown: one row per ad set per day. Each
# row carries its campaign, so campaign totals are a grouping of these rather
# than a second pull. Names are kept per day because Meta lets them change.
adset_daily_insights = Table(
    "adset_daily_insights",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("adset_id", String, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("adset_name", String, nullable=True),
    Column("campaign_id", String, nullable=False),
    Column("campaign_name", String, nullable=True),
    Column("spend", Float, nullable=False),
    Column("impressions", Integer, nullable=False),
    Column("clicks", Integer, nullable=False),
    Column("conversions", Integer, nullable=False),
)

# Columns added after the tables first shipped. `create_all` will not alter an
# existing table, so these run as idempotent ALTERs on every init.
_ADDED_COLUMNS = (
    ("daily_insights", "reach", "INTEGER"),
    ("daily_insights", "purchase_value", "DOUBLE PRECISION"),
    ("account_targets", "goal_metric", "VARCHAR"),
    ("account_targets", "target_value", "DOUBLE PRECISION"),
)


def get_engine() -> Engine:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///dashboard.db")
    return create_engine(database_url)


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)

    # `create_all` creates missing tables but never alters existing ones, so
    # columns added after first ship are applied here. Checked against the live
    # schema rather than using dialect-specific "IF NOT EXISTS" syntax.
    inspector = inspect(engine)
    existing = {
        table: {col["name"] for col in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }

    with engine.begin() as conn:
        for table, column, sql_type in _ADDED_COLUMNS:
            if table in existing and column not in existing[table]:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))

        # Carry forward goals set before the metric became configurable: they
        # were all cost per result by definition.
        if "account_targets" in existing and "target_cpr" in existing["account_targets"]:
            conn.execute(
                text(
                    "UPDATE account_targets "
                    "SET target_value = target_cpr, "
                    "    goal_metric = COALESCE(goal_metric, 'cost_per_result') "
                    "WHERE target_value IS NULL AND target_cpr IS NOT NULL"
                )
            )


def upsert_daily_insight(
    engine: Engine,
    account_id: str,
    insight_date: date,
    spend: float,
    impressions: int,
    clicks: int,
    conversions: int,
    reach: int | None = None,
    purchase_value: float | None = None,
) -> None:
    values = {
        "account_id": account_id,
        "date": insight_date,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "reach": reach,
        "purchase_value": purchase_value,
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
            "reach": stmt.excluded.reach,
            "purchase_value": stmt.excluded.purchase_value,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def upsert_account_target(
    engine: Engine,
    account_id: str,
    client_name: str | None,
    goal_metric: str | None,
    target_value: float | None,
) -> None:
    values = {
        "account_id": account_id,
        "client_name": client_name,
        "goal_metric": goal_metric,
        "target_value": target_value,
        "updated_at": datetime.now(timezone.utc),
    }
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(account_targets).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id"],
        set_={
            "client_name": stmt.excluded.client_name,
            "goal_metric": stmt.excluded.goal_metric,
            "target_value": stmt.excluded.target_value,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def upsert_adset_daily_insight(
    engine: Engine,
    account_id: str,
    adset_id: str,
    insight_date: date,
    adset_name: str | None,
    campaign_id: str,
    campaign_name: str | None,
    spend: float,
    impressions: int,
    clicks: int,
    conversions: int,
) -> None:
    values = {
        "account_id": account_id,
        "adset_id": adset_id,
        "date": insight_date,
        "adset_name": adset_name,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
    }
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(adset_daily_insights).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id", "adset_id", "date"],
        set_={
            "adset_name": stmt.excluded.adset_name,
            "campaign_id": stmt.excluded.campaign_id,
            "campaign_name": stmt.excluded.campaign_name,
            "spend": stmt.excluded.spend,
            "impressions": stmt.excluded.impressions,
            "clicks": stmt.excluded.clicks,
            "conversions": stmt.excluded.conversions,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)
