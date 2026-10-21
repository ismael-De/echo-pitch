import json

import pytest

from analytics import (possession, pass_difficulty, pass_summary, xg_timeline, pressure_index, momentum,
                       key_moments, control_vs_chaos, pressure_shifts, rhythm, match_state)
from generator import generate_match


@pytest.fixture(scope="module")
def m():
    return generate_match(seed=53, home="AVR", away="CLW", match_no=1)


def test_possession_sums_to_100(m):
    p = possession(m[1])
    assert abs(p["home"] + p["away"] - 100) < 0.2 and 30 < p["home"] < 70


def test_pass_difficulty_range_and_order(m):
    easy = {"team": "home", "x": 30, "y": 34, "end_x": 35, "end_y": 34, "pressure_level": 0.0}
    hard = {"team": "home", "x": 60, "y": 34, "end_x": 95, "end_y": 30, "pressure_level": 0.9}
    assert pass_difficulty(easy) < 20 < 70 < pass_difficulty(hard) <= 100
    ps = pass_summary(m[1])
    assert 70 < ps["home"]["completion_pct"] < 90


def test_xg_timeline_monotonic(m):
    tl = xg_timeline(m[1])
    for a, b in zip(tl, tl[1:]):
        assert b["home_xg"] >= a["home_xg"] and b["away_xg"] >= a["away_xg"]


def test_series_bounds(m):
    for r in momentum(m[1]):
        assert -1 <= r["momentum"] <= 1
    for r in pressure_index(m[1]):
        assert 0 <= r["home"] <= 100 and 0 <= r["away"] <= 100
    for r in control_vs_chaos(m[1]):
        assert r["label"] in ("controlled", "chaotic", "contested")
    assert all(r["label"] in ("fast and direct", "slow build-up", "steady") for r in rhythm(m[1]))
    assert isinstance(pressure_shifts(m[1]), list)


def test_key_moments_include_all_goals(m):
    meta, ev = m
    km = key_moments(ev)
    goals = [k for k in km if k["kind"] == "goal"]
    assert len(goals) == sum(meta["final_score"].values())
    assert any(k["kind"] == "key_save" for k in km)
    assert all(0 <= k["importance"] <= 1 for k in km)


def test_match_state_json_and_prefix(m):
    meta, ev = m
    full = match_state(ev, meta)
    json.dumps(full)
    assert full["score"] == meta["final_score"]
    half = match_state(ev[: len(ev) // 2], meta)
    assert half["events_processed"] == len(ev) // 2
    assert sum(half["shots"].values()) <= sum(full["shots"].values())
    assert match_state([], meta)["score"] == {"home": 0, "away": 0}
