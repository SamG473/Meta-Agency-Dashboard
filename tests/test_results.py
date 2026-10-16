"""Unit tests for ingest/results.py: what counts as a "result" for an ad set.

Meta reports every action an ad produced (clicks, likes, video views, leads)
in one `actions` list. Summing that list once made results read about twice
reality. A result is only the outcome the ad set is optimising for.
"""
import pytest

from ingest.results import daily_basis, resolve_results


def _resolve(goal, *, actions=None, cost_per_action_type=None, reach=None,
             spend=30.0, custom_event_type=None, warn=None):
    return resolve_results(
        goal=goal,
        custom_event_type=custom_event_type,
        actions=actions,
        thruplay_actions=None,
        cost_per_action_type=cost_per_action_type,
        reach=reach,
        spend=spend,
        warn=warn or (lambda message: None),
    )


def test_lead_goal_counts_only_leads_not_every_action():
    actions = [
        {"action_type": "link_click", "value": "40"},
        {"action_type": "post_engagement", "value": "55"},
        {"action_type": "onsite_conversion.lead_grouped", "value": "6"},
    ]
    cost = [{"action_type": "onsite_conversion.lead_grouped", "value": "5.0"}]
    results, basis, action_type, cost_per_result = _resolve(
        "LEAD_GENERATION", actions=actions, cost_per_action_type=cost)
    assert results == 6                    # not 101, the old inflated sum
    assert basis == "action"
    assert action_type == "onsite_conversion.lead_grouped"
    assert cost_per_result == 5.0          # Meta's own figure, preferred


def test_cost_is_computed_when_meta_reports_none():
    actions = [{"action_type": "link_click", "value": "40"}]
    results, _, _, cost_per_result = _resolve("LINK_CLICKS", actions=actions)
    assert results == 40
    assert cost_per_result == 0.75         # £30 / 40 clicks


def test_goal_with_no_results_today_is_zero_with_no_cost():
    # Spent money, no leads landed: zero results is true, a price is not.
    results, basis, _, cost_per_result = _resolve("LEAD_GENERATION", actions=[])
    assert (results, basis, cost_per_result) == (0, "action", None)


def test_reach_goal_counts_people_and_prices_per_thousand():
    results, basis, action_type, cost = _resolve("REACH", reach=1500)
    assert (results, basis, action_type) == (1500, "reach", "reach")
    assert cost == 20.0                    # £30 per 1,500 people = £20 per 1,000


def test_pixel_purchase_goal_names_its_event():
    actions = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "3"}]
    results, _, action_type, _ = _resolve(
        "OFFSITE_CONVERSIONS", custom_event_type="PURCHASE", actions=actions)
    assert action_type == "offsite_conversion.fb_pixel_purchase"
    assert results == 3


@pytest.mark.parametrize("goal, event", [
    ("SOME_NEW_GOAL", None),               # a goal Meta added that we don't know
    ("OFFSITE_CONVERSIONS", None),         # a pixel goal with no event named
])
def test_unmapped_goal_warns_instead_of_guessing(goal, event):
    warnings = []
    actions = [{"action_type": "link_click", "value": "40"}]
    result = _resolve(goal, custom_event_type=event, actions=actions,
                      warn=warnings.append)
    assert result == (None, "unmapped", None, None)
    assert len(warnings) == 1


@pytest.mark.parametrize("bases, expected", [
    (["action", "action"], "action"),
    (["reach"], "reach"),
    (["action", "reach"], "mixed"),
    (["action", "unmapped"], "action"),    # unmapped ad sets don't dilute
    (["unmapped"], "unmapped"),
    ([], None),                            # no ad sets delivered at all
])
def test_daily_basis(bases, expected):
    assert daily_basis(bases) == expected
