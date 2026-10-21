"""Deterministic stats layer for Echo Pitch.

Conventions
-----------
* ``events`` is a list of event dicts as produced by ``generator`` (time-ordered).
* Home attacks towards x=105, away towards x=0. ``_att_x`` converts to the team's attacking frame.
* Minute buckets use the displayed match minute (``minute`` field), so first-half stoppage
  shows as 45+ and the second half starts at 45.
* All outputs are plain dicts/lists of numbers and strings (JSON-ready).
"""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, pstdev
from typing import Any, Iterable

Event = dict[str, Any]
SIDES = ("home", "away")
BIG_CHANCE_XG = 0.30
ON_BALL = {"pass", "carry", "shot"}


def _other(side: str) -> str:
    return "away" if side == "home" else "home"


def _att_x(e: Event, key: str = "x") -> float:
    v = e[key]
    return v if e["team"] == "home" else 105.0 - v


def _abs_t(e: Event) -> int:
    return e["minute"] * 60 + e["second"]


def match_clock(e: Event) -> str:
    """Broadcast-style clock string, e.g. '45+2'' or '67''."""
    m = e["minute"]
    if e.get("period") == 1 and m >= 45:
        return f"45+{m - 44}'"
    if e.get("period") == 2 and m >= 90:
        return f"90+{m - 89}'"
    return f"{m + 1}'"


def _bucket(e: Event, size_min: int) -> tuple[int, int]:
    """(period, window start). First-half stoppage gets its own 45' window in period 1, so it never mixes
    with the opening minutes of the second half (which also start at minute 45, period 2)."""
    b = (e["minute"] // size_min) * size_min
    p = e.get("period", 1)
    return (p, min(b, 45)) if p == 1 else (p, max(b, 45))


def _windows(events: list[Event], size_min: int) -> dict[tuple[int, int], list[Event]]:
    out: dict[tuple[int, int], list[Event]] = defaultdict(list)
    for e in events:
        out[_bucket(e, size_min)].append(e)
    return dict(sorted(out.items()))


def _wrow(key: tuple[int, int], size_min: int) -> dict[str, Any]:
    p, b = key
    label = "45+'" if (p == 1 and b == 45) else ("90+'" if b >= 90 else f"{b}-{b + size_min}'")
    return {"minute": b, "period": p, "label": label}


def _duration_min(evs: list[Event], size_min: int) -> float:
    """Actual covered minutes of a window (stoppage windows are short); 1..size_min."""
    if not evs:
        return float(size_min)
    span = (_abs_t(evs[-1]) - _abs_t(evs[0])) / 60 + 0.5
    return max(1.0, min(float(size_min), span))


def timeline_minute(e: Event, h1_last_minute: int = 45) -> int:
    """Monotonic minute index across both halves (second half shifted past first-half stoppage)."""
    if e.get("period", 1) == 1:
        return e["minute"]
    return e["minute"] + max(0, h1_last_minute + 1 - 45)


# ------------------------------------------------------------------ possession
def possession(events: list[Event]) -> dict[str, float]:
    """Time-weighted possession %, attributing the gap until the next event to the team on the ball."""
    owner, last_t, acc = None, None, {"home": 0.0, "away": 0.0}
    for e in events:
        t = _abs_t(e) + (10_000 if e.get("period") == 2 else 0)
        if owner and last_t is not None:
            acc[owner] += min(max(t - last_t, 0), 20)  # cap dead-ball gaps
        if e["type"] in ON_BALL or e["type"] == "possession_change":
            owner = e["team"]
        if e["type"] == "goal":
            owner = None
        last_t = t
    tot = sum(acc.values()) or 1.0
    return {s: round(100 * acc[s] / tot, 1) for s in SIDES}


# ------------------------------------------------------------------ passing
def pass_difficulty(e: Event) -> float:
    """0-100 difficulty rating for one pass: distance, pressure, forward progress and target zone."""
    d = math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"])
    prog = _att_x(e, "end_x") - _att_x(e, "x")
    zone = max(0.0, (_att_x(e, "end_x") - 70) / 35)
    score = 30 * min(d / 40, 1) + 30 * e["pressure_level"] + 20 * max(0.0, min(prog / 30, 1)) + 20 * zone
    return round(min(score, 100), 1)


def pass_summary(events: list[Event]) -> dict[str, dict[str, float]]:
    """Per team: passes, completion %, mean difficulty, and completed passes with difficulty >= 60."""
    out = {}
    for s in SIDES:
        ps = [e for e in events if e["type"] == "pass" and e["team"] == s]
        comp = [e for e in ps if e["outcome"] == "complete"]
        diffs = [pass_difficulty(e) for e in ps]
        out[s] = {"passes": len(ps), "completed": len(comp),
                  "completion_pct": round(100 * len(comp) / len(ps), 1) if ps else 0.0,
                  "avg_difficulty": round(mean(diffs), 1) if diffs else 0.0,
                  "hard_passes_completed": sum(pass_difficulty(e) >= 60 for e in comp)}
    return out


# ------------------------------------------------------------------ xG
def xg_timeline(events: list[Event]) -> list[dict[str, Any]]:
    """Cumulative xG after every shot: [{minute, clock, team, player, xg, outcome, home_xg, away_xg}]."""
    cum = {"home": 0.0, "away": 0.0}
    out = []
    for e in events:
        if e["type"] == "shot":
            cum[e["team"]] += e["xg"]
            out.append({"event_id": e["event_id"], "minute": e["minute"], "clock": match_clock(e), "team": e["team"],
                        "player": e["player_name"], "xg": e["xg"], "outcome": e["outcome"],
                        "home_xg": round(cum["home"], 2), "away_xg": round(cum["away"], 2)})
    return out


# ------------------------------------------------------------------ pressure
def pressure_index(events: list[Event], window_min: int = 5) -> list[dict[str, Any]]:
    """Per window, 0-100 index of how hard each team presses: pressure events x mean intensity + ball wins."""
    out = []
    for w, evs in _windows(events, window_min).items():
        row: dict[str, Any] = _wrow(w, window_min)
        dur = _duration_min(evs, window_min)
        for s in SIDES:
            pr = [e for e in evs if e["team"] == s and e["type"] == "pressure"]
            wins = sum(e["team"] == s and e["type"] == "tackle" and e["outcome"] == "won" for e in evs)
            intensity = mean(e["pressure_level"] for e in pr) if pr else 0.0
            row[s] = round(min(100.0, (len(pr) * intensity * 6 + wins * 8) * 5 / max(dur, 2.5)), 1)
        out.append(row)
    return out


# ------------------------------------------------------------------ momentum
def _threat(e: Event) -> float:
    t = e["type"]
    if t == "shot":
        return 1.0 + 3 * e["xg"]
    if t in ("pass", "carry") and e["outcome"] in ("complete", "success") and _att_x(e, "end_x") > 75:
        return 0.35
    if t == "tackle" and e["outcome"] == "won":
        return 0.25
    if t == "goal":
        return 1.5
    return 0.0


def momentum(events: list[Event], window_min: int = 5, tau_min: float = 3.0, prior: float = 4.0) -> list[dict[str, Any]]:
    """Per-minute momentum in [-1, 1] (positive = home on top).

    Threat is accumulated with exponential time decay (``tau_min``) on a monotonic timeline (first-half
    stoppage and the second half never overlap), and ``prior`` regularises sparse minutes such as
    stoppage time so a single action cannot swing the curve to an extreme.
    ``window_min`` is kept for API compatibility; the decay horizon is ~3*tau.
    """
    if not events:
        return []
    h1_last = max((e["minute"] for e in events if e.get("period", 1) == 1), default=45)
    per_t: dict[int, dict[str, float]] = defaultdict(lambda: {"home": 0.0, "away": 0.0})
    label: dict[int, tuple[int, int]] = {}
    for e in events:
        t = timeline_minute(e, h1_last)
        per_t[t][e["team"]] += _threat(e)
        label[t] = (e.get("period", 1), e["minute"])
    out, h, a, prev = [], 0.0, 0.0, 0.0
    decay = math.exp(-1 / tau_min)
    last_period, last_minute = 1, 0
    for t in range(0, max(per_t) + 1):
        h, a = h * decay + per_t[t]["home"] if t in per_t else h * decay, a * decay + per_t[t]["away"] if t in per_t else a * decay
        if t in label:
            last_period, last_minute = label[t]
        else:
            last_minute += 1
        clk = match_clock({"period": last_period, "minute": last_minute})
        raw = (h - a) / (h + a + prior)
        prev = 0.6 * raw + 0.4 * prev  # light output smoothing for display and narration
        out.append({"t": t, "minute": last_minute, "period": last_period, "clock": clk, "momentum": round(prev, 3)})
    return out


# ------------------------------------------------------------------ key moments
def key_moments(events: list[Event]) -> list[dict[str, Any]]:
    """Candidate moments for narration, each with a type, an importance score (0-1) and a machine-readable reason."""
    out = []
    by_id = {e["event_id"]: i for i, e in enumerate(events)}
    score = {"home": 0, "away": 0}
    for i, e in enumerate(events):
        base = {"event_id": e["event_id"], "minute": e["minute"], "clock": match_clock(e), "team": e["team"],
                "player": e["player_name"]}
        if e["type"] == "goal":
            score[e["team"]] += 1
            late = e["minute"] >= 80
            out.append({**base, "kind": "goal", "importance": 1.0 if late else 0.9, "xg": e["xg"],
                        "score_after": dict(score),
                        "reason": f"goal from {e['xg']:.2f} xG" + (" late in the match" if late else "")})
        elif e["type"] == "shot" and e["outcome"] != "goal" and e["xg"] >= BIG_CHANCE_XG:
            out.append({**base, "kind": "big_chance_missed", "importance": round(0.5 + e["xg"] / 2, 2), "xg": e["xg"],
                        "reason": f"{e['xg']:.2f} xG chance {e['outcome'].replace('_', ' ')}"})
        elif e["type"] == "save":
            shot = events[i - 1] if i else None
            xg = shot["xg"] if shot and shot["type"] == "shot" else 0.0
            if e["outcome"] == "wonder_save" or xg >= 0.15:
                out.append({**base, "kind": "key_save", "importance": round(min(1.0, 0.55 + xg), 2), "xg_prevented": xg,
                            "reason": f"keeper denied a {xg:.2f} xG shot"})
    pi = pressure_index(events, 5)
    for s in SIDES:
        vals = [r[s] for r in pi]
        if len(vals) >= 4:
            mu, sd = mean(vals), pstdev(vals) or 1.0
            for r in pi:
                if r[s] >= mu + 1.5 * sd:
                    out.append({"event_id": None, "minute": r["minute"], "period": r["period"], "clock": r["label"],
                                "team": s, "player": None, "kind": "pressure_spike",
                                "importance": round(min(0.8, 0.4 + (r[s] - mu) / (4 * sd)), 2),
                                "reason": f"pressing index {r[s]} vs match average {mu:.1f}"})
    out.sort(key=lambda m: (m["minute"], by_id.get(m["event_id"], 0)))
    return out


# ------------------------------------------------------------------ explainability
def control_vs_chaos(events: list[Event], window_min: int = 5) -> list[dict[str, Any]]:
    """Per window: control (completion x chain length) vs chaos (turnovers, duels, fouls per minute) -> label."""
    out = []
    for w, evs in _windows(events, window_min).items():
        dur = _duration_min(evs, window_min)
        passes = [e for e in evs if e["type"] == "pass"]
        comp = sum(e["outcome"] == "complete" for e in passes) / len(passes) if passes else 0
        turnovers = sum(e["type"] == "possession_change" for e in evs)
        duels = sum(e["type"] in ("tackle", "foul") for e in evs)
        chain = len(passes) / (turnovers + 1)
        control = min(1.0, comp * min(chain / 6, 1.0))
        chaos = max(0.0, min(1.0, ((turnovers + duels) / dur - 2.6) / 2.4))  # calibrated: ~13 -> 0, ~26 -> 1 per 5'
        label = "controlled" if control - chaos > 0.1 else ("chaotic" if chaos - control > 0.25 else "contested")
        dom = {s: sum(e["team"] == s for e in passes) for s in SIDES}
        out.append({**_wrow(w, window_min), "control": round(control, 2), "chaos": round(chaos, 2), "label": label,
                    "in_control": max(dom, key=dom.get) if label == "controlled" else None})
    return out


def pressure_shifts(events: list[Event], window_min: int = 5, threshold: float = 15.0) -> list[dict[str, Any]]:
    """Windows where the pressing advantage flips between teams by at least ``threshold`` index points."""
    pi = pressure_index(events, window_min)
    out, prev = [], None
    for r in pi:
        diff = r["home"] - r["away"]
        if prev is not None and abs(diff - prev) >= threshold and (diff > 0) != (prev > 0):
            leader = "home" if diff > 0 else "away"
            out.append({"minute": r["minute"], "period": r["period"], "label": r["label"], "from_team": _other(leader), "to_team": leader,
                        "swing": round(abs(diff - prev), 1),
                        "reason": f"{leader} took over the press ({r[leader]} vs {r[_other(leader)]})"})
        prev = diff
    return out


def rhythm(events: list[Event], window_min: int = 5) -> list[dict[str, Any]]:
    """Game rhythm per window: tempo (events/min), mean passes per possession, label fast/steady/slow."""
    out = []
    for w, evs in _windows(events, window_min).items():
        tempo = len(evs) / _duration_min(evs, window_min)
        seq = sum(e["type"] == "pass" for e in evs) / (sum(e["type"] == "possession_change" for e in evs) + 1)
        label = "fast and direct" if tempo > 23 and seq < 4 else ("slow build-up" if seq >= 6 else "steady")
        out.append({**_wrow(w, window_min), "tempo": round(tempo, 1), "passes_per_possession": round(seq, 1), "label": label})
    return out


# ------------------------------------------------------------------ aggregate
def match_state(events: list[Event], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full JSON snapshot of the match so far (pass a prefix of events for a live state)."""
    score = {s: sum(e["type"] == "goal" and e["team"] == s for e in events) for s in SIDES}
    shots = {s: [e for e in events if e["type"] == "shot" and e["team"] == s] for s in SIDES}
    last = events[-1] if events else None
    mom = momentum(events)
    return {
        "match_id": events[0]["match_id"] if events else (meta or {}).get("match_id"),
        "teams": {s: meta[s]["name"] for s in SIDES} if meta else None,
        "events_processed": len(events),
        "clock": match_clock(last) if last else "0'",
        "score": score,
        "possession_pct": possession(events),
        "shots": {s: len(shots[s]) for s in SIDES},
        "shots_on_target": {s: sum(e["outcome"] in ("goal", "saved") for e in shots[s]) for s in SIDES},
        "xg": {s: round(sum(e["xg"] for e in shots[s]), 2) for s in SIDES},
        "passing": pass_summary(events),
        "fouls": {s: sum(e["type"] == "foul" and e["team"] == s for e in events) for s in SIDES},
        "momentum_now": mom[-1]["momentum"] if mom else 0.0,
        "momentum": mom,
        "xg_timeline": xg_timeline(events),
        "pressure_index": pressure_index(events),
        "key_moments": key_moments(events),
        "control_vs_chaos": control_vs_chaos(events),
        "pressure_shifts": pressure_shifts(events),
        "rhythm": rhythm(events),
    }
