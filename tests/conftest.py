"""Shared test setup: a throwaway database, small fake data, and an API client.

Safety first. `app.main` builds its database engine at import time from
DATABASE_URL, and calls load_dotenv(), which would read the real Supabase URL
from a local .env. load_dotenv() never overrides a variable that is already
set, so the environment is pinned to harmless dummies below, BEFORE the app is
imported. The app's engine is then swapped for a test engine per test.

The test database is TEST_DATABASE_URL when set (Postgres, in CI), otherwise an
in-memory SQLite database that vanishes when the tests finish.
"""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEMO_MODE"] = "false"
os.environ["META_ACCESS_TOKEN"] = "dummy-test-token"
os.environ["META_AD_ACCOUNT_IDS"] = "act_test_dummy"

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.main as main  # noqa: E402
from ingest.db import (  # noqa: E402
    init_db,
    metadata,
    set_daily_results,
    upsert_account_target,
    upsert_adset_daily_insight,
    upsert_daily_insight,
)

TODAY = date.today()


def _make_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        # One shared connection, or each new connection would get its own
        # empty in-memory database.
        return create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    # Guard against pointing the suite at a real database: tests drop every
    # table when they finish.
    name = make_url(url).database or ""
    if "test" not in name:
        raise RuntimeError(
            f"TEST_DATABASE_URL names database {name!r}; refusing to run tests "
            "against a database whose name does not contain 'test'."
        )
    return create_engine(url)


@pytest.fixture(scope="session")
def engine():
    eng = _make_engine()
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine, monkeypatch):
    """Empty tables for one test, wired into the app, dropped afterwards."""
    init_db(engine)
    monkeypatch.setattr(main, "engine", engine)
    yield engine
    metadata.drop_all(engine)


@pytest.fixture
def client(db):
    return TestClient(main.app)


def add_day(
    engine, account_id, day, *, spend, impressions, clicks, results=None, basis=None, reach=None
):
    """One account-day, written the way the ingest writes it: the account row
    first, then its results summed from the ad sets."""
    upsert_daily_insight(
        engine,
        account_id,
        day,
        spend,
        impressions,
        clicks,
        conversions=0,
        reach=reach,
    )
    set_daily_results(engine, account_id, day, results, basis)


@pytest.fixture
def seeded(db):
    """Three fake clients, small enough to check every figure by hand.

    act_test_cpr    judged on cost per result, target £5.00. Last 3 days:
                    £30 spend, 12 results -> £2.50 per result, on track.
                    One older day (4 days ago) for the previous-period
                    comparison: £20 spend, 2 results.
    act_test_reach  judged on reach, target 10,000 people, no goal period set,
                    so its pace cannot be judged. Awareness ad set.
    act_test_empty  a target but no delivery at all.
    """
    for offset in range(3):
        day = TODAY - timedelta(days=offset)
        add_day(
            db,
            "act_test_cpr",
            day,
            spend=10.0,
            impressions=1000,
            clicks=20,
            results=4,
            basis="action",
            reach=800,
        )
        upsert_adset_daily_insight(
            db,
            "act_test_cpr",
            "adset_leads",
            day,
            adset_name="Lead form",
            campaign_id="camp_1",
            campaign_name="Test leads campaign",
            spend=10.0,
            impressions=1000,
            clicks=20,
            conversions=0,
            reach=800,
            optimization_goal="LEAD_GENERATION",
            result_action_type="onsite_conversion.lead_grouped",
            results=4,
            cost_per_result=2.5,
        )

        add_day(
            db,
            "act_test_reach",
            day,
            spend=5.0,
            impressions=600,
            clicks=3,
            results=500,
            basis="reach",
            reach=500,
        )
        upsert_adset_daily_insight(
            db,
            "act_test_reach",
            "adset_reach",
            day,
            adset_name="Broad reach",
            campaign_id="camp_2",
            campaign_name="Test reach campaign",
            spend=5.0,
            impressions=600,
            clicks=3,
            conversions=0,
            reach=500,
            optimization_goal="REACH",
            result_action_type="reach",
            results=500,
            cost_per_result=10.0,
        )

    previous_day = TODAY - timedelta(days=4)
    add_day(
        db,
        "act_test_cpr",
        previous_day,
        spend=20.0,
        impressions=2000,
        clicks=20,
        results=2,
        basis="action",
        reach=1500,
    )
    upsert_adset_daily_insight(
        db,
        "act_test_cpr",
        "adset_leads",
        previous_day,
        adset_name="Lead form",
        campaign_id="camp_1",
        campaign_name="Test leads campaign",
        spend=20.0,
        impressions=2000,
        clicks=20,
        conversions=0,
        reach=1500,
        optimization_goal="LEAD_GENERATION",
        result_action_type="onsite_conversion.lead_grouped",
        results=2,
        cost_per_result=10.0,
    )

    upsert_account_target(db, "act_test_cpr", "Test Client CPR", "cost_per_result", 5.0)
    upsert_account_target(db, "act_test_reach", "Test Client Reach", "reach", 10000.0)
    upsert_account_target(db, "act_test_empty", "Test Client Empty", "cost_per_result", 3.0)
    return db
