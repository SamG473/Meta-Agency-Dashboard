"""Unit tests for the derived-metric functions in app/main.py.

Pure functions, no database: each takes numbers and returns a number or None.
The rule running through all of them is that "nothing to divide by" is None
(no data), never 0, because zero is a claim about performance.
"""
from datetime import date, timedelta

import pytest

from app.main import (
    AT_RISK_PACE,
    _change,
    _ctr,
    _evaluate_rate,
    _metric_actual,
    _pace,
    _state_from_pace,
)


def test_ctr_is_clicks_over_impressions_as_a_percentage():
    assert _ctr(clicks=25, impressions=1000) == 2.5


def test_ctr_with_zero_clicks_is_zero():
    # Shown 1,000 times, clicked never: a genuine 0%.
    assert _ctr(clicks=0, impressions=1000) == 0.0


def test_ctr_with_zero_impressions_is_none():
    # Never shown: there is no rate at all, and 0% would read as a bad ad.
    assert _ctr(clicks=0, impressions=0) is None


# --- Cost per result, ROAS, leads, reach: _metric_actual -------------------

def test_cost_per_result_is_spend_over_results():
    assert _metric_actual("cost_per_result", spend=30.0, results=12, reach=None,
                          revenue=None, results_basis="action") == 2.5


def test_cost_per_result_with_zero_results_is_none():
    # £30 spent, nothing bought: no price exists, and dividing would crash.
    assert _metric_actual("cost_per_result", spend=30.0, results=0, reach=None,
                          revenue=None, results_basis="action") is None


def test_cost_per_result_with_zero_spend_is_zero():
    # Results for free is a real (if unusual) figure, not missing data.
    assert _metric_actual("cost_per_result", spend=0.0, results=5, reach=None,
                          revenue=None, results_basis="action") == 0.0


def test_cost_per_result_never_ingested_is_none():
    assert _metric_actual("cost_per_result", spend=30.0, results=None, reach=None,
                          revenue=None, results_basis=None) is None


@pytest.mark.parametrize("metric", ["cost_per_result", "cost_per_lead", "leads"])
@pytest.mark.parametrize("basis", ["reach", "unmapped"])
def test_conversion_metrics_refuse_awareness_results(metric, basis):
    # For a reach campaign "results" are people reached. Dividing spend by
    # them would print a cost per lead that is really a cost per person.
    assert _metric_actual(metric, spend=30.0, results=1500, reach=1500,
                          revenue=None, results_basis=basis) is None


def test_roas_is_revenue_over_spend():
    assert _metric_actual("roas", spend=30.0, results=None, reach=None,
                          revenue=75.0, results_basis=None) == 2.5


@pytest.mark.parametrize("spend, revenue", [(0.0, 75.0), (30.0, None)])
def test_roas_without_spend_or_revenue_is_none(spend, revenue):
    assert _metric_actual("roas", spend=spend, results=None, reach=None,
                          revenue=revenue, results_basis=None) is None


def test_reach_passes_through_and_keeps_missing_distinct_from_zero():
    assert _metric_actual("reach", 10.0, None, 1500, None, None) == 1500.0
    assert _metric_actual("reach", 10.0, None, 0, None, None) == 0.0
    assert _metric_actual("reach", 10.0, None, None, None, None) is None


# --- Rate goals against target: _evaluate_rate -----------------------------
# Deviation is signed so that positive always means worse, whichever way the
# metric runs: over target is bad for a cost, under target is bad for ROAS.

@pytest.mark.parametrize("metric, target, actual, state, deviation", [
    ("cost_per_result", 5.0, 2.5, "on_track", -0.5),   # half the cost: good
    ("cost_per_result", 5.0, 6.0, "behind", 0.2),      # 20% over: bad
    ("cost_per_result", 5.0, 5.0, "on_track", 0.0),    # exactly on target
    ("roas", 2.0, 3.0, "on_track", -0.5),              # more return: good
    ("roas", 2.0, 1.5, "behind", 0.25),                # 25% short: bad
])
def test_rate_goal_direction(metric, target, actual, state, deviation):
    assert _evaluate_rate(metric, target, actual) == (state, deviation)


def test_rate_goal_with_no_actual_is_no_data():
    assert _evaluate_rate("cost_per_result", 5.0, None) == ("no_data", None)


# --- Pacing a cumulative goal: _pace and _state_from_pace ------------------

TODAY = date(2026, 10, 15)


def test_pace_three_days_into_a_ten_day_period():
    pace = _pace(target=100, actual=30, start=TODAY - timedelta(days=2),
                 end=TODAY + timedelta(days=7), today=TODAY)
    assert pace["total_days"] == 10
    assert pace["elapsed_days"] == 3       # today counts as elapsed
    assert pace["expected_to_date"] == 30.0
    assert pace["pace_ratio"] == 1.0
    assert pace["ended"] is False


def test_pace_before_the_period_starts_has_no_ratio():
    # Nothing is due yet, so there is nothing to divide by.
    pace = _pace(target=100, actual=0, start=TODAY + timedelta(days=1),
                 end=TODAY + timedelta(days=10), today=TODAY)
    assert pace["elapsed_days"] == 0
    assert pace["pace_ratio"] is None
    assert _state_from_pace(pace, 100, 0) == ("not_started", None)


def _running(ratio):
    return {"ended": False, "pace_ratio": ratio}


@pytest.mark.parametrize("ratio, state", [
    (1.2, "on_track"),
    (1.0, "on_track"),               # exactly on pace counts as on track
    (AT_RISK_PACE, "at_risk"),       # the at-risk floor is inclusive
    (AT_RISK_PACE - 0.01, "behind"),
    (0.0, "behind"),
])
def test_pace_state_boundaries(ratio, state):
    assert _state_from_pace(_running(ratio), target=100, actual=0)[0] == state


@pytest.mark.parametrize("actual, state", [(100, "met"), (150, "met"), (99, "missed")])
def test_ended_period_is_met_or_missed_against_the_full_target(actual, state):
    assert _state_from_pace({"ended": True}, target=100, actual=actual) == (state, None)


# --- Period-over-period change: _change ------------------------------------

def test_change_is_proportional():
    assert _change(current=15, previous=10) == 0.5
    assert _change(current=5, previous=10) == -0.5


@pytest.mark.parametrize("current, previous", [(10, 0), (None, 10), (10, None)])
def test_change_without_a_comparable_previous_is_none(current, previous):
    # Up from zero is not an infinite % change; it is no comparison at all.
    assert _change(current, previous) is None
