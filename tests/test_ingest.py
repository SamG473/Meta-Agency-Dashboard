"""The nightly ingest (ingest/run.py), with the Meta SDK replaced by a fake.

Nothing here reaches Meta: AdAccount and FacebookAdsApi are swapped for
stand-ins that return whatever each test hands them, and the database is the
throwaway test one from conftest.py.
"""
import sys

import pytest
from sqlalchemy import create_engine, func, select

import ingest.run as run
from conftest import TODAY
from ingest.db import adset_daily_insights, campaigns, daily_insights, ingest_heartbeat

# Shaped like a real id, so the log masking below has digits to keep.
ACCOUNT = "act_100200300400"


class FakeAdAccount:
    """Answers the four calls the ingest makes, from class-level fixtures."""
    Field = run.AdAccount.Field  # the real field names; only the calls are fake
    campaigns = []
    adsets = []
    account_insights = []
    adset_insights = []

    def __init__(self, account_id):
        self.account_id = account_id

    def api_get(self, fields):
        return {"account_status": 1}

    def get_campaigns(self, fields, params):
        return list(self.campaigns)

    def get_ad_sets(self, fields, params):
        return list(self.adsets)

    def get_insights(self, fields, params):
        rows = self.adset_insights if params.get("level") == "adset" else self.account_insights
        return list(rows)


class FakeApi:
    @staticmethod
    def init(**kwargs):
        pass


@pytest.fixture
def ingest(db, monkeypatch):
    """Run the nightly ingest's main() against the fakes and the test DB."""
    monkeypatch.setattr(run, "AdAccount", FakeAdAccount)
    monkeypatch.setattr(run, "FacebookAdsApi", FakeApi)
    monkeypatch.setattr(run, "get_engine", lambda: db)
    # Never read the local .env: it holds the real credentials.
    monkeypatch.setattr(run, "load_dotenv", lambda: None)
    monkeypatch.setenv("META_ACCESS_TOKEN", "dummy-test-token")
    monkeypatch.setenv("META_AD_ACCOUNT_IDS", ACCOUNT)
    monkeypatch.setattr(sys, "argv", ["ingest.run"])  # no flags: yesterday
    for name in ("campaigns", "adsets", "account_insights", "adset_insights"):
        monkeypatch.setattr(FakeAdAccount, name, [])

    def _run():
        run.main()
        return db

    return _run


def _count(db, table):
    with db.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar()


def _one_day_of_delivery():
    day = str(TODAY.replace(day=1))
    FakeAdAccount.campaigns = [{"id": "c1", "name": "Test", "effective_status": "ACTIVE"}]
    FakeAdAccount.adsets = [{"id": "as1", "optimization_goal": "LINK_CLICKS"}]
    FakeAdAccount.account_insights = [{
        "date_start": day, "spend": "12.50", "impressions": "1000",
        "clicks": "40", "actions": [{"action_type": "link_click", "value": "40"}],
    }]
    FakeAdAccount.adset_insights = [{
        "date_start": day, "adset_id": "as1", "campaign_id": "c1",
        "spend": "12.50", "impressions": "1000", "clicks": "40",
        "actions": [{"action_type": "link_click", "value": "40"}],
    }]


def test_no_campaigns_and_no_delivery_exits_cleanly(ingest):
    # Today's real state: no campaigns on any account, so Meta returns empty
    # lists everywhere. The run should finish normally and write nothing.
    db = ingest()
    assert _count(db, daily_insights) == 0
    assert _count(db, adset_daily_insights) == 0
    assert _count(db, campaigns) == 0


def test_one_day_of_delivery_is_written(ingest):
    # The same fakes with data in them, so the empty test above is known to be
    # exercising the real write path rather than passing because nothing ran.
    _one_day_of_delivery()
    db = ingest()
    assert _count(db, daily_insights) == 1
    assert _count(db, adset_daily_insights) == 1
    with db.connect() as conn:
        row = conn.execute(select(daily_insights)).one()
    assert (row.spend, row.results, row.results_basis) == (12.5, 40, "action")


def test_no_delivery_says_so_in_the_log(ingest, capsys):
    ingest()
    out = capsys.readouterr().out
    assert "Database: connected" in out
    assert "Checking 1 account(s)" in out
    assert "checked 1 account(s), 0 campaign(s)" in out
    assert "wrote 0 account row(s) and 0 ad set row(s)" in out
    assert "nothing to write" in out


def test_log_carries_no_client_figures_or_full_account_ids(ingest, capsys):
    # The repo is public, and so are its Actions logs. Counts are fine; a
    # client's spend, delivery or full account id is not.
    _one_day_of_delivery()
    ingest()
    out = capsys.readouterr().out
    for figure in ("12.5", "1000", "spend", "impressions", "clicks", "results="):
        assert figure not in out
    assert ACCOUNT not in out
    assert "act_…0400" in out


def test_unreachable_database_fails_with_one_clear_line(ingest, monkeypatch):
    # What a paused Supabase project looks like from here: the first database
    # call fails. The run must still fail (exit non-zero, so GitHub marks it
    # red), but with a line saying what broke rather than only a traceback.
    unreachable = create_engine("sqlite:////no/such/directory/dashboard.db")
    monkeypatch.setattr(run, "get_engine", lambda: unreachable)
    with pytest.raises(SystemExit) as exit_info:
        ingest()
    assert exit_info.value.code != 0
    assert "Database: could not connect" in str(exit_info.value.code)


# --- Heartbeat ---------------------------------------------------------------
# One row the ingest rewrites on every run, so the database sees a write each
# night even when there is no delivery to store (Supabase's free tier pauses
# an idle project).

def _heartbeat(db):
    with db.connect() as conn:
        return conn.execute(select(ingest_heartbeat)).all()


def test_heartbeat_is_one_row_updated_by_every_run(ingest):
    db = ingest()
    [first] = _heartbeat(db)
    assert first.last_run_at is not None
    assert first.last_success_at is not None

    ingest()
    [second] = _heartbeat(db)              # still one row, not one per run
    assert second.last_run_at > first.last_run_at
    assert second.last_success_at > first.last_success_at


def test_failed_run_records_the_attempt_but_not_a_success(ingest, db, monkeypatch):
    # Meta failing (an expired token, say) still counts as database activity,
    # but must not move the "last good run" time.
    def broken(self, fields, params):
        raise RuntimeError("Meta said no")
    monkeypatch.setattr(FakeAdAccount, "get_campaigns", broken)

    with pytest.raises(RuntimeError):
        ingest()
    [row] = _heartbeat(db)
    assert row.last_run_at is not None
    assert row.last_success_at is None
