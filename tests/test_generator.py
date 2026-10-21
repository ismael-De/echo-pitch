import json
import subprocess
import sys

import pytest

from generator import generate_match, xg_model
from generator.core import EVENT_TYPES

KEYS = ["match_id", "event_id", "minute", "second", "team", "player_id", "player_name", "type", "x", "y",
        "end_x", "end_y", "outcome", "speed_kmh", "pressure_level", "xg"]


@pytest.fixture(scope="module", params=[42, 43, 44])
def match(request):
    return generate_match(seed=request.param)


def test_schema(match):
    meta, events = match
    ids = {p["player_id"] for s in ("home", "away") for p in meta[s]["lineup"]}
    assert len(ids) == 22
    for e in events:
        for k in KEYS:
            assert k in e
        assert e["type"] in EVENT_TYPES
        assert e["team"] in ("home", "away") and e["player_id"] in ids
        assert 0 <= e["x"] <= 105 and 0 <= e["y"] <= 68
        assert 0 <= e["pressure_level"] <= 1
        if e["type"] == "shot":
            assert 0 < e["xg"] < 1


def test_time_ordering(match):
    _, events = match
    t = [(e["period"], e["minute"] * 60 + e["second"]) for e in events]
    assert t == sorted(t)
    assert len({e["event_id"] for e in events}) == len(events)


def test_goals_match_score(match):
    meta, events = match
    for s in ("home", "away"):
        assert sum(e["type"] == "goal" and e["team"] == s for e in events) == meta["final_score"][s]
        assert sum(e["type"] == "shot" and e["outcome"] == "goal" and e["team"] == s for e in events) == meta["final_score"][s]


def test_realism(match):
    _, events = match
    assert 1400 <= len(events) <= 2200
    passes = [e for e in events if e["type"] == "pass"]
    acc = sum(e["outcome"] == "complete" for e in passes) / len(passes)
    assert 0.72 <= acc <= 0.88
    for s in ("home", "away"):
        assert 5 <= sum(e["type"] == "shot" and e["team"] == s for e in events) <= 25


def test_deterministic():
    assert generate_match(seed=7) == generate_match(seed=7)


def test_xg_monotonic():
    assert xg_model(99, 34) > xg_model(94, 34) > xg_model(85, 34) > xg_model(75, 34)
    assert xg_model(94, 34) > xg_model(94, 10)


def test_cli(tmp_path):
    subprocess.run([sys.executable, "-m", "generator", "--seed", "1", "--out", str(tmp_path), "--matches", "1"], check=True)
    meta = json.loads((tmp_path / "EP-2026-001_meta.json").read_text())
    lines = (tmp_path / "EP-2026-001_events.jsonl").read_text().splitlines()
    assert meta["synthetic"] and len(lines) > 1000


def test_unique_names_across_clubs(match):
    meta, _ = match
    names = [p["name"] for s in ("home", "away") for p in meta[s]["lineup"]]
    assert len(set(names)) == 22


def test_ball_continuity(match):
    """An on-ball action following a completed pass/carry by the same team starts where the ball ended."""
    _, ev = match
    for a, b in zip(ev, ev[1:]):
        if (a["type"] in ("pass", "carry") and a["outcome"] in ("complete", "success")
                and b["team"] == a["team"] and b["type"] in ("pass", "carry", "shot")):
            assert abs(a["end_x"] - b["x"]) < 0.2 and abs(a["end_y"] - b["y"]) < 0.2, (a["event_id"], b["event_id"])


def test_shot_imbalance_soft_cap():
    for seed in range(40, 60):
        _, ev = generate_match(seed=seed)
        h = sum(e["type"] == "shot" and e["team"] == "home" for e in ev)
        a = sum(e["type"] == "shot" and e["team"] == "away" for e in ev)
        assert abs(h - a) <= 12, (seed, h, a)
