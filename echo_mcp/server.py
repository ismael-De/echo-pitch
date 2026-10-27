"""MCP server exposing Echo Pitch's deterministic stats and the fact-check Verifier.

Transports:
  stdio:            python -m echo_mcp                    (GitHub Copilot CLI / VS Code / local agents)
  streamable HTTP:  mounted by the web app at /mcp/       (Foundry agents, remote MCP clients)

Tools: list_matches, get_match_stats, get_key_moments, get_event, verify_commentary.
All data is synthetic (fictional teams and players).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import analytics as A
from agents.verifier import Verifier

DATA_DIR = Path(os.environ.get("ECHO_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


@lru_cache(maxsize=16)
def _load(match_id: str) -> tuple[dict, list[dict]]:
    meta_p, ev_p = DATA_DIR / f"{match_id}_meta.json", DATA_DIR / f"{match_id}_events.jsonl"
    if not meta_p.exists() or not ev_p.exists():
        raise ValueError(f"unknown match {match_id}; call list_matches first")
    return json.loads(meta_p.read_text()), [json.loads(l) for l in ev_p.read_text().splitlines() if l]


def _upto(events: list[dict], minute: int | None) -> list[dict]:
    """Events before match minute `minute` (timeline minutes, so first-half stoppage stays in the first half)."""
    if minute is None:
        return events
    h1 = max((e["minute"] for e in events if e["period"] == 1), default=45)
    return [e for e in events if A.stats.timeline_minute(e, h1) < minute]


def _named(st: dict, meta: dict) -> dict:
    names = {s: meta[s]["name"] for s in ("home", "away")}
    by = lambda d: {names[k]: v for k, v in d.items()}
    return {"clock": st["clock"], "score": by(st["score"]), "possession_pct": by(st["possession_pct"]),
            "shots": by(st["shots"]), "shots_on_target": by(st["shots_on_target"]), "xg": by(st["xg"]),
            "pass_completion_pct": {names[k]: v["completion_pct"] for k, v in st["passing"].items()},
            "fouls": by(st["fouls"]), "events_processed": st["events_processed"]}


def list_matches() -> list[dict]:
    """List the synthetic demo matches (match_id, teams, venue, kickoff)."""
    out = []
    for p in sorted(DATA_DIR.glob("*_meta.json")):
        m = json.loads(p.read_text())
        out.append({"match_id": m["match_id"], "home": m["home"]["name"], "away": m["away"]["name"],
                    "venue": m["venue"], "kickoff": m["kickoff"], "synthetic": True})
    return out


def get_match_stats(match_id: str, minute: int | None = None) -> dict:
    """Deterministic live stats (score, possession, shots, xG, pass %, fouls) up to a match minute (default: full time)."""
    meta, ev = _load(match_id)
    return _named(A.match_state(_upto(ev, minute), meta), meta)


def get_key_moments(match_id: str, minute: int | None = None) -> list[dict]:
    """Key moments (goals, big chances, saves, pressure spikes) with clock, player, team and xG, up to a minute."""
    meta, ev = _load(match_id)
    names = {s: meta[s]["name"] for s in ("home", "away")}
    return [{**m, "team": names.get(m.get("team"), m.get("team"))} for m in A.key_moments(_upto(ev, minute))]


def get_event(match_id: str, event_id: str) -> dict:
    """One raw match event by event_id (player, team, type, outcome, xG, coordinates)."""
    _, ev = _load(match_id)
    for e in ev:
        if e["event_id"] == event_id:
            return e
    raise ValueError(f"unknown event {event_id}")


def verify_commentary(match_id: str, text: str, minute: int | None = None, event_id: str | None = None) -> dict:
    """Fact-check a commentary line with the Echo Pitch Verifier (deterministic, no LLM).

    Every number must match the match stats/key moments (or the given event) and every player name must
    belong to those facts. Returns ok, problems, and the evidence (which fact supports each claim)."""
    meta, ev = _load(match_id)
    facts: dict = {"stats": get_match_stats(match_id, minute), "key_moments": get_key_moments(match_id, minute)}
    if event_id:
        e = get_event(match_id, event_id)
        facts["event"] = {**e, "clock": A.match_clock(e), "team_name": meta[e["team"]]["name"]}
    return Verifier(meta).check(text, facts).as_dict()


TOOLS = [list_matches, get_match_stats, get_key_moments, get_event, verify_commentary]


def build_server(http: bool = False) -> FastMCP:
    mcp = FastMCP("echo-pitch", instructions="Synthetic football match stats and a deterministic commentary "
                  "fact-checker. Call list_matches first.", stateless_http=http, json_response=http,
                  streamable_http_path="/",
                  transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    for fn in TOOLS:
        mcp.tool()(fn)
    return mcp


def main() -> None:
    build_server().run("stdio")
