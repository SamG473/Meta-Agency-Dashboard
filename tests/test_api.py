"""API tests: the real FastAPI routes, against the seeded test database."""

import os
import subprocess
import sys
from datetime import timedelta

import pytest

from conftest import TODAY


def _account(board, account_id):
    return next(a for a in board["accounts"] if a["account_id"] == account_id)


def test_manual_goal_period_is_used_for_pace(client, seeded):
    # A 10-day period, 3 days in: 10,000 reach should be 3,000 delivered by
    # now. The seed delivered 500 a day, 1,500 in all: half the pace.
    response = client.put(
        "/api/targets/act_test_reach",
        json={
            "goal_metric": "reach",
            "target_value": 10000,
            "period_start": str(TODAY - timedelta(days=2)),
            "period_end": str(TODAY + timedelta(days=7)),
        },
    )
    assert response.status_code == 200

    reach = _account(client.get("/api/board").json(), "act_test_reach")
    assert reach["state"] == "behind"
    assert reach["pace"]["source"] == "manual"
    assert reach["pace"]["expected_to_date"] == 3000.0
    assert reach["pace"]["pace_ratio"] == 0.5


def test_put_rejects_period_that_ends_before_it_starts(client, seeded):
    # A period that ends before it starts used to be saved, and the board then
    # summed delivery over an empty date range and labelled a client that HAD
    # delivered "no_data". Reject it at the door instead.
    response = client.put(
        "/api/targets/act_test_reach",
        json={
            "goal_metric": "reach",
            "target_value": 10000,
            "period_start": str(TODAY),
            "period_end": str(TODAY - timedelta(days=1)),
        },
    )
    assert response.status_code == 422
    assert client.get("/api/board").status_code == 200


@pytest.mark.parametrize("path", ["/api/board", "/api/analytics"])
@pytest.mark.parametrize("days", [-1, 1_000_000])
def test_out_of_range_days_is_a_422_not_a_crash(client, seeded, path, days):
    # A million days back is before year 1: date arithmetic overflowed and the
    # request died with a 500. Bad input should be the caller's error.
    assert client.get(f"{path}?days={days}").status_code == 422


# --- GET /api/board ---------------------------------------------------------


def test_board_judges_each_client_against_its_own_goal(client, seeded):
    board = client.get("/api/board?days=30").json()
    assert [a["account_id"] for a in board["accounts"]] == [
        "act_test_cpr",
        "act_test_empty",
        "act_test_reach",
    ]

    cpr = _account(board, "act_test_cpr")
    assert cpr["spend"] == 50.0
    assert cpr["results"] == 14
    assert cpr["actual_value"] == 3.57  # £50 / 14, against a £5 target
    assert cpr["state"] == "on_track"
    assert cpr["ctr"] == 1.6  # 80 clicks / 5,000 impressions

    # A reach goal with no period end cannot be paced, and is not compared
    # against its full target instead.
    reach = _account(board, "act_test_reach")
    assert reach["state"] == "no_end_date"
    assert reach["actual_value"] == 1500.0

    # A target but no delivery: it has not fallen short, it has not run.
    empty = _account(board, "act_test_empty")
    assert empty["state"] == "no_data"
    assert empty["actual_value"] is None
    assert empty["ctr"] is None  # no impressions, so no rate


def test_board_window_changes_the_figures(client, seeded):
    # The 3-day window leaves out the older, more expensive day.
    cpr = _account(client.get("/api/board?days=3").json(), "act_test_cpr")
    assert cpr["spend"] == 30.0
    assert cpr["actual_value"] == 2.5


def test_board_portfolio_totals(client, seeded):
    portfolio = client.get("/api/board?days=30").json()["portfolio"]
    assert portfolio["spend"] == 65.0
    assert portfolio["accounts_tracked"] == 3
    assert portfolio["cpm"] == 9.56  # £65 / 6,800 impressions x 1,000
    # Only the CPR client's pace can be judged; the others are excluded rather
    # than counted as failures.
    assert (portfolio["on_pace"], portfolio["pace_judged"], portfolio["pace_excluded"]) == (1, 1, 2)
    # Unknown, not zero, when no campaign has ever been synced.
    assert portfolio["active_campaigns"] is None


def test_board_with_an_empty_database(client):
    board = client.get("/api/board").json()
    assert board["accounts"] == []
    assert board["portfolio"]["spend"] == 0.0
    assert board["portfolio"]["cpm"] is None  # no impressions to divide by
    assert board["retention"]["days_stored"] == 0


# --- GET /api/analytics -----------------------------------------------------


def test_analytics_compares_with_the_previous_period(client, seeded):
    data = client.get("/api/analytics?account_id=act_test_cpr&days=3").json()
    current, previous, change = data["current"], data["previous"], data["change"]

    assert (current["spend"], current["results"], current["cpa"]) == (30.0, 12, 2.5)
    assert (previous["spend"], previous["results"], previous["cpa"]) == (20.0, 2, 10.0)
    assert change["cpa"] == -0.75  # £10 -> £2.50
    assert change["spend"] == 0.5
    assert current["cost_per_1k_reach"] is None  # no awareness spend to price
    assert data["has_conversion_spend"] is True
    assert data["has_awareness_spend"] is False

    [row] = data["breakdown"]["rows"]
    assert (row["cost"], row["cost_label"]) == (2.5, "per result")
    assert len(data["daily"]) == 3


def test_analytics_prices_an_awareness_client_per_thousand_reached(client, seeded):
    data = client.get("/api/analytics?account_id=act_test_reach&days=3").json()
    assert data["current"]["cpa"] is None  # never called a CPA
    assert data["current"]["cost_per_1k_reach"] == 10.0  # £15 / 1,500 people
    [row] = data["breakdown"]["rows"]
    assert row["cost_label"] == "per 1,000 reached"


def test_analytics_all_history_has_no_comparison(client, seeded):
    data = client.get("/api/analytics?account_id=act_test_cpr&days=0").json()
    assert data["previous"] is None
    assert data["change"] is None
    assert data["current"]["spend"] == 50.0


def test_analytics_unknown_account_is_404_naming_it(client, seeded):
    response = client.get("/api/analytics?account_id=act_nope")
    assert response.status_code == 404
    assert "act_nope" in response.json()["detail"]


# --- PUT /api/targets and GET /api/metrics ----------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"goal_metric": "clicks", "target_value": 5},  # not a goal metric
        {"goal_metric": "cost_per_result", "target_value": 0},  # must be > 0
    ],
)
def test_put_target_rejects_invalid_goals(client, seeded, body):
    assert client.put("/api/targets/act_test_cpr", json=body).status_code == 422


def test_put_target_changes_the_boards_verdict(client, seeded):
    # Tighten the target below the actual £3.57: now the client is behind.
    response = client.put(
        "/api/targets/act_test_cpr",
        json={
            "client_name": "Renamed Test Client",
            "goal_metric": "cost_per_result",
            "target_value": 2.0,
        },
    )
    assert response.status_code == 200

    cpr = _account(client.get("/api/board?days=30").json(), "act_test_cpr")
    assert cpr["state"] == "behind"
    assert cpr["client_name"] == "Renamed Test Client"


def test_metrics_lists_the_goal_registry(client):
    keys = {m["key"] for m in client.get("/api/metrics").json()}
    assert keys == {"leads", "roas", "cost_per_lead", "cost_per_result", "reach"}


def test_api_never_loads_the_meta_sdk():
    # The dashboard reads only from the database. If any route pulled in the
    # Meta SDK, it would be one step from a live API call on page load.
    # Checked in a fresh interpreter: the ingest tests import the SDK into
    # this one, so sys.modules here says nothing about the app on its own.
    script = (
        "import sys\n"
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "client = TestClient(app)\n"
        "assert client.get('/api/board').status_code == 200\n"
        "assert client.get('/api/analytics').status_code == 200\n"
        "assert 'facebook_business' not in sys.modules\n"
    )
    # Demo mode gives the routes an in-memory database to read.
    env = {**os.environ, "DEMO_MODE": "true", "DATABASE_URL": "sqlite://"}
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
