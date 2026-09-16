"""Normalized storage for pulled Meta insights.

Defaults to a local SQLite file so early dev isn't blocked on a Supabase
signup (CLAUDE.md allows this). Set DATABASE_URL to a Postgres URL to point
at Supabase instead — no query changes needed either way.
"""
import os
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
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
    # `conversions` above is the legacy sum of every action type Meta reported,
    # which counts unrelated outcomes together. `results` is the honest figure:
    # the sum of each ad set's own optimisation outcome for that day (see
    # ingest/results.py). Nothing in the app reads `conversions` any more.
    Column("results", Integer, nullable=True),
    # "action", "reach", "mixed" or "unmapped" — what those results are.
    Column("results_basis", String, nullable=True),
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
    Column("reach", Integer, nullable=True),
    # What this ad set optimises for, and what that makes a result: the action
    # type counted, the count itself, and Meta's cost for it. An awareness ad
    # set carries "reach" as its action type and a cost per 1,000 reached.
    Column("optimization_goal", String, nullable=True),
    Column("result_action_type", String, nullable=True),
    Column("results", Integer, nullable=True),
    Column("cost_per_result", Float, nullable=True),
)

# Each campaign's current state, refreshed on every run. Not a time series: a
# campaign is active or it is not, and that is what the board counts. Campaigns
# Meta no longer returns are deleted rather than left behind reading ACTIVE.
campaigns = Table(
    "campaigns",
    metadata,
    Column("account_id", String, primary_key=True),
    Column("campaign_id", String, primary_key=True),
    Column("name", String, nullable=True),
    # Meta's own rollup — ACTIVE, PAUSED, ARCHIVED, DELETED, IN_PROCESS or
    # WITH_ISSUES — which already accounts for pauses above the campaign.
    Column("effective_status", String, nullable=True),
    # False when the ad account itself is not active, which leaves campaigns
    # reading ACTIVE while nothing can deliver.
    Column("account_active", Boolean, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# Columns added after the tables first shipped. `create_all` will not alter an
# existing table, so these run as idempotent ALTERs on every init.
_ADDED_COLUMNS = (
    ("daily_insights", "reach", "INTEGER"),
    ("daily_insights", "purchase_value", "DOUBLE PRECISION"),
    ("daily_insights", "results", "INTEGER"),
    ("daily_insights", "results_basis", "VARCHAR"),
    ("account_targets", "goal_metric", "VARCHAR"),
    ("account_targets", "target_value", "DOUBLE PRECISION"),
    ("adset_daily_insights", "reach", "INTEGER"),
    ("adset_daily_insights", "optimization_goal", "VARCHAR"),
    ("adset_daily_insights", "result_action_type", "VARCHAR"),
    ("adset_daily_insights", "results", "INTEGER"),
    ("adset_daily_insights", "cost_per_result", "DOUBLE PRECISION"),
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
    reach: int | None = None,
    optimization_goal: str | None = None,
    result_action_type: str | None = None,
    results: int | None = None,
    cost_per_result: float | None = None,
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
        "reach": reach,
        "optimization_goal": optimization_goal,
        "result_action_type": result_action_type,
        "results": results,
        "cost_per_result": cost_per_result,
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
            "reach": stmt.excluded.reach,
            "optimization_goal": stmt.excluded.optimization_goal,
            "result_action_type": stmt.excluded.result_action_type,
            "results": stmt.excluded.results,
            "cost_per_result": stmt.excluded.cost_per_result,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def upsert_campaign(
    engine: Engine,
    account_id: str,
    campaign_id: str,
    name: str | None,
    effective_status: str | None,
    account_active: bool,
) -> None:
    values = {
        "account_id": account_id,
        "campaign_id": campaign_id,
        "name": name,
        "effective_status": effective_status,
        "account_active": account_active,
        "updated_at": datetime.now(timezone.utc),
    }
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    stmt = insert(campaigns).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id", "campaign_id"],
        set_={
            "name": stmt.excluded.name,
            "effective_status": stmt.excluded.effective_status,
            "account_active": stmt.excluded.account_active,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def prune_campaigns(engine: Engine, account_id: str, keep: set[str]) -> int:
    """Drop campaigns Meta stopped returning for this account — deleted ones,
    and any that fell out of the API's default view. Leaving them behind would
    keep counting a campaign that no longer exists.
    """
    statement = delete(campaigns).where(campaigns.c.account_id == account_id)
    if keep:
        statement = statement.where(campaigns.c.campaign_id.not_in(keep))
    with engine.begin() as conn:
        return conn.execute(statement).rowcount


def set_daily_results(
    engine: Engine,
    account_id: str,
    insight_date: date,
    results: int | None,
    results_basis: str | None,
) -> None:
    """An account-day's results, summed from that day's ad sets. Written after
    the ad set pull because the account-level row cannot know it: each ad set
    counts a different outcome, and Meta's account-level actions array mixes
    them all together.
    """
    with engine.begin() as conn:
        conn.execute(
            daily_insights.update()
            .where(
                daily_insights.c.account_id == account_id,
                daily_insights.c.date == insight_date,
            )
            .values(results=results, results_basis=results_basis)
        )
