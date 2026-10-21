"""Echo Pitch API: match data, live stats state and SSE replay (no LLM yet).

Run:  uvicorn app.main:app --reload      (data dir via ECHO_DATA_DIR, default ./data)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents import MatchOrchestrator, Prefs, Settings
from analytics import match_state
from analytics.stats import _bucket as A_bucket

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DATA_DIR = Path(os.environ.get("ECHO_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
app = FastAPI(title="Echo Pitch API", version="0.1.0")


# ------------------------------------------------------------------ data access
@lru_cache(maxsize=32)
def _load(match_id: str) -> tuple[dict, list[dict]]:
    meta_p, ev_p = DATA_DIR / f"{match_id}_meta.json", DATA_DIR / f"{match_id}_events.jsonl"
    if not meta_p.exists() or not ev_p.exists():
        raise HTTPException(404, f"unknown match {match_id}")
    return json.loads(meta_p.read_text()), [json.loads(l) for l in ev_p.read_text().splitlines() if l]


def _game_seconds(events: list[dict]) -> list[float]:
    """Monotonic elapsed seconds per event (handles first-half stoppage overlapping minute 45)."""
    h1_end = max((e["minute"] * 60 + e["second"] for e in events if e["period"] == 1), default=2700)
    return [e["minute"] * 60 + e["second"] if e["period"] == 1 else h1_end + 1 + (e["minute"] * 60 + e["second"] - 2700)
            for e in events]


# ------------------------------------------------------------------ replay sessions
class ReplayRequest(BaseModel):
    match_id: str
    speed: float = Field(30, ge=10, le=60, description="playback speed multiplier (10-60x)")
    start_minute: int = Field(0, ge=0, le=120)


class Replay:
    def __init__(self, match_id: str, speed: float, start_minute: int):
        self.id, self.match_id, self.speed = uuid.uuid4().hex[:12], match_id, speed
        self.meta, self.events = _load(match_id)
        self.t = _game_seconds(self.events)
        # map the displayed match minute to elapsed replay time (second half if start_minute >= 45)
        cands = [t for e, t in zip(self.events, self.t)
                 if e["minute"] >= start_minute and (e["period"] == 2 or start_minute < 45)]
        self.offset = (min(cands) if cands else self.t[-1]) if start_minute else 0.0
        self.started = time.monotonic()

    def game_time(self) -> float:
        return self.offset + (time.monotonic() - self.started) * self.speed

    def position(self) -> int:
        """Number of events that have 'happened' at the current replay time."""
        gt = self.game_time()
        return sum(1 for t in self.t if t <= gt)

    @property
    def finished(self) -> bool:
        return self.position() >= len(self.events)


REPLAYS: dict[str, Replay] = {}


def _replay(rid: str) -> Replay:
    if rid not in REPLAYS:
        raise HTTPException(404, f"unknown replay {rid}")
    return REPLAYS[rid]


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ------------------------------------------------------------------ endpoints
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/matches")
def list_matches():
    out = []
    for p in sorted(DATA_DIR.glob("*_meta.json")):
        m = json.loads(p.read_text())
        out.append({"match_id": m["match_id"], "home": m["home"]["name"], "away": m["away"]["name"],
                    "venue": m["venue"], "kickoff": m["kickoff"]})
    return out


@app.get("/api/matches/{match_id}/meta")
def get_meta(match_id: str):
    return _load(match_id)[0]


@app.get("/api/matches/{match_id}/events")
def get_events(match_id: str, upto: int | None = Query(None, ge=0, description="first N events")):
    ev = _load(match_id)[1]
    return ev if upto is None else ev[:upto]


@app.get("/api/matches/{match_id}/stats")
def get_stats(match_id: str, upto: int | None = Query(None, ge=0, description="state after first N events")):
    meta, ev = _load(match_id)
    return match_state(ev if upto is None else ev[:upto], meta)


@app.post("/api/replays", status_code=201)
def create_replay(req: ReplayRequest):
    r = Replay(req.match_id, req.speed, req.start_minute)
    REPLAYS[r.id] = r
    return {"replay_id": r.id, "match_id": r.match_id, "speed": r.speed,
            "stream_url": f"/api/replays/{r.id}/stream", "state_url": f"/api/replays/{r.id}/state"}


@app.get("/api/replays/{rid}/state")
def replay_state(rid: str):
    r = _replay(rid)
    n = r.position()
    st = match_state(r.events[:n], r.meta)
    st.update(replay_id=rid, speed=r.speed, finished=n >= len(r.events), game_seconds=round(r.game_time(), 1))
    return st


@app.delete("/api/replays/{rid}")
def delete_replay(rid: str):
    _replay(rid)
    del REPLAYS[rid]
    return {"deleted": rid}


@app.get("/api/config")
def config():
    st = Settings.from_env()
    return {"llm_mode": st.mode, "model": st.model if st.mode == "foundry" else None, "warning": st.warning,
            "speeds": [10, 20, 30, 45, 60]}


@app.get("/api/replays/{rid}/stream")
async def replay_stream(rid: str, stats_every: int = Query(25, ge=1, le=500),
                        persona: str = Query("fan", pattern="^(fan|analyst)$"),
                        lang: str = Query("en", pattern="^(en|ar)$"),
                        club: str | None = Query(None, pattern="^(home|away)$"),
                        player: str | None = None, from_now: bool = False, agents: bool = True):
    """SSE stream for one viewer.

    Events: `meta`, `match_event` (raw), `commentary`, `moment_card`, `overlay`, `stats`, `agent_trace`,
    `recap`, `end`. Persona/lang/club/player personalise the agent output; `from_now=true` joins the replay
    at its current position (used when the viewer changes preferences mid-match).
    """
    r = _replay(rid)

    async def gen():
        sent = r.position() if from_now else sum(1 for t in r.t if t < r.offset)
        orch = MatchOrchestrator(r.meta, Prefs(persona, lang, club, player)) if agents else None
        if orch:
            for e in r.events[:sent]:  # warm the shared state silently when joining mid-match
                orch.events.append(e)
                if e["type"] == "goal":
                    orch.score[e["team"]] += 1
            orch.last_window = A_bucket(r.events[sent - 1], 5) if sent else (1, 0)
            orch.last_insight_min = r.events[sent - 1]["minute"] if sent else 0
        yield _sse("meta", {"match_id": r.match_id, "speed": r.speed, "home": r.meta["home"]["name"],
                            "away": r.meta["away"]["name"], "total_events": len(r.events), "joined_at": sent,
                            "llm_mode": orch.settings.mode if orch else None})
        if orch:
            yield _sse("stats", orch.compact_stats())
            if not sent:
                for name, data in await orch.start():
                    yield _sse(name, data)
        while sent < len(r.events):
            pos = r.position()
            while sent < pos:
                e = r.events[sent]
                yield _sse("match_event", e)
                sent += 1
                if orch:
                    for name, data in await orch.on_event(e):
                        yield _sse(name, data)
                elif sent % stats_every == 0:
                    s = match_state(r.events[:sent], r.meta)
                    yield _sse("stats", {k: s[k] for k in ("clock", "score", "possession_pct", "xg", "shots",
                                                           "momentum_now", "events_processed")})
            if sent < len(r.events):
                wait = (r.t[sent] - r.game_time()) / r.speed
                await asyncio.sleep(min(max(wait, 0.01), 1.0))
                if orch:  # stream LLM upgrades as soon as they finish, between events
                    for name, data in orch.drain():
                        yield _sse(name, data)
        if orch:
            for name, data in await orch.finish():
                yield _sse(name, data)
        if orch and orch.uses_llm:
            yield _sse("usage", orch.usage())
        yield _sse("end", {"final_score": r.meta["final_score"]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
