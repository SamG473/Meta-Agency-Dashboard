"""What counts as a result, per ad set optimisation goal.

Meta's `actions` array carries every action an ad produced — link clicks, page
engagement, video views, purchases — so summing it counts unrelated outcomes
together. That was this project's headline defect: "results" ran at roughly
twice reality and every cost per result derived from it read half price.

A result is the single outcome the ad set is optimising for. For awareness
goals there is no conversion action at all: the result is people reached, and
the cost figure is never a cost per conversion.
"""
import sys

# Goals whose outcome is delivery itself.
AWARENESS_GOALS = {"REACH", "IMPRESSIONS"}

# optimization_goal -> the one action_type that counts as a result.
ACTION_TYPE_BY_GOAL = {
    "LINK_CLICKS": "link_click",
    "LANDING_PAGE_VIEWS": "landing_page_view",
    "POST_ENGAGEMENT": "post_engagement",
    "PAGE_LIKES": "like",
    "APP_INSTALLS": "mobile_app_install",
    "VIDEO_VIEWS": "video_view",
}

# Lead forms report under either name depending on where the form lives, so
# take whichever Meta actually returned that day.
LEAD_ACTION_TYPES = ("onsite_conversion.lead_grouped", "lead")

# Pixel conversions name their event: OFFSITE_CONVERSIONS plus a promoted
# object of PURCHASE becomes offsite_conversion.fb_pixel_purchase.
OFFSITE_GOALS = {"OFFSITE_CONVERSIONS", "CONVERSIONS"}

# ThruPlays are not in `actions`; they arrive in their own insights field.
THRUPLAY = "thruplay"

RESULT_LABELS = {
    "link_click": "Link clicks",
    "landing_page_view": "Landing page views",
    "post_engagement": "Post engagements",
    "like": "Page likes",
    "mobile_app_install": "App installs",
    "video_view": "Video views",
    THRUPLAY: "ThruPlays",
    "lead": "Leads",
    "onsite_conversion.lead_grouped": "Leads",
    "reach": "People reached",
}


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def result_label(action_type: str | None) -> str:
    """A human name for what was counted, for the UI's unit captions."""
    if action_type is None:
        return "Unmapped goal"
    if action_type.startswith("offsite_conversion.fb_pixel_"):
        event = action_type.rsplit("_", 1)[-1].replace("-", " ")
        return f"Pixel {event}s"
    return RESULT_LABELS.get(action_type, action_type.replace("_", " ").capitalize())


def result_action_type(
    goal: str | None, custom_event_type: str | None = None, actions: list[dict] | None = None
) -> str | None:
    """The action type that counts as a result for this goal, or None when the
    goal has no mapping. "reach" means the reach metric, not an action.
    """
    if goal in AWARENESS_GOALS:
        return "reach"
    if goal == "THRUPLAY":
        return THRUPLAY
    if goal == "LEAD_GENERATION":
        present = {a.get("action_type") for a in actions or []}
        for candidate in LEAD_ACTION_TYPES:
            if candidate in present:
                return candidate
        # Nothing landed today; name the on-platform type so a zero is still
        # attributed to the right outcome.
        return LEAD_ACTION_TYPES[0]
    if goal in OFFSITE_GOALS:
        if not custom_event_type:
            return None
        return f"offsite_conversion.fb_pixel_{custom_event_type.lower()}"
    return ACTION_TYPE_BY_GOAL.get(goal)


def _value(rows: list[dict] | None, action_type: str) -> float | None:
    for row in rows or []:
        if row.get("action_type") == action_type:
            return float(row.get("value", 0))
    return None


def resolve_results(
    *,
    goal: str | None,
    custom_event_type: str | None,
    actions: list[dict] | None,
    thruplay_actions: list[dict] | None,
    cost_per_action_type: list[dict] | None,
    reach: int | None,
    spend: float,
    warn=_warn,
) -> tuple[int | None, str, str | None, float | None]:
    """(results, basis, action_type, cost_per_result) for one ad set on one day.

    `basis` is "action" for a counted conversion, "reach" for an awareness goal,
    or "unmapped" when the goal has no mapping — and there results stay None
    rather than falling back to summing every action type.
    """
    action_type = result_action_type(goal, custom_event_type, actions)

    if action_type == "reach":
        results = int(reach) if reach is not None else None
        # Per 1,000 people, the only cost figure that means anything here. It is
        # never a cost per conversion and must never be labelled one.
        cost = round(spend / results * 1000, 2) if results else None
        return results, "reach", "reach", cost

    if action_type is None:
        reason = (
            "no promoted_object.custom_event_type on the ad set"
            if goal in OFFSITE_GOALS
            else "no result mapping"
        )
        warn(f"optimization_goal {goal!r}: {reason}, so results are left unset")
        return None, "unmapped", None, None

    # ThruPlays arrive in video_thruplay_watched_actions, itself typed
    # "video_view", rather than in the actions array.
    rows = thruplay_actions if action_type == THRUPLAY else actions
    counted = _value(rows, "video_view" if action_type == THRUPLAY else action_type)
    results = int(counted) if counted is not None else 0

    # Meta's own cost per this action where it reported one, rather than our
    # own division; they can differ on attribution.
    reported = None if action_type == THRUPLAY else _value(cost_per_action_type, action_type)
    if reported is not None:
        cost = round(reported, 2)
    else:
        cost = round(spend / results, 2) if results else None

    return results, "action", action_type, cost


def daily_basis(bases: list[str]) -> str | None:
    """One account-day's basis, from the ad sets that delivered that day."""
    kinds = {b for b in bases if b in ("action", "reach")}
    if not kinds:
        return "unmapped" if bases else None
    if kinds == {"action"}:
        return "action"
    if kinds == {"reach"}:
        return "reach"
    return "mixed"
