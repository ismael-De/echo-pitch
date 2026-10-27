"""Echo Pitch API: match data, live stats, and the SSE replay with the agent stream.

Run:  uvicorn app.main:app --reload      (data dir via ECHO_DATA_DIR, default ./data)
"""
from __future__ import annotations

import asyncio
import json
import re
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from contextlib import asynccontextmanager

from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents import MatchOrchestrator, Prefs, Settings
from app.budget import Budget, client_id
from analytics import match_state
from analytics.stats import _bucket as A_bucket

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

DATA_DIR = Path(os.environ.get("ECHO_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
from echo_mcp import build_server, http_app  # noqa: E402
from app import tts  # noqa: E402

MCP = build_server()
_MCP_APP = http_app(MCP)


@asynccontextmanager
async def _lifespan(_app):
    async with MCP.session_manager.run():
        yield


app = FastAPI(title="Echo Pitch API", version="0.2.0", lifespan=_lifespan)


# ------------------------------------------------------------------ data access
MATCH_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RateLimit:
    """Tiny per-client sliding-window limiter (in-memory; one replica). Stops /api/tts being a free speech API
    and stops scripted replay creation from evicting other visitors' sessions."""
    def __init__(self, n: int, per: float):
        self.n, self.per, self.hits = n, per, {}

    def check(self, request: Request):
        now, key = time.monotonic(), client_id(request.headers, request.client.host if request.client else None)
        q = [t for t in self.hits.get(key, []) if now - t < self.per]
        if len(q) >= self.n:
            raise HTTPException(429, "rate limit: slow down", headers={"Retry-After": str(int(self.per))})
        q.append(now); self.hits[key] = q
        if len(self.hits) > 5000:
            self.hits.clear()


TTS_RL, REPLAY_RL, VERIFY_RL = RateLimit(90, 60), RateLimit(20, 60), RateLimit(60, 60)


@lru_cache(maxsize=32)
def _load(match_id: str) -> tuple[dict, list[dict]]:
    if not MATCH_RE.match(match_id):
        raise HTTPException(404, "unknown match")
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
        self.audit: list[dict] = []   # Verifier verdicts + producer decisions (enterprise audit log)

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
BUDGET = Budget()


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
def create_replay(req: ReplayRequest, request: Request):
    REPLAY_RL.check(request)
    r = Replay(req.match_id, req.speed, req.start_minute)
    while len(REPLAYS) >= BUDGET.max_replays:  # dicts keep insertion order: evict the oldest
        REPLAYS.pop(next(iter(REPLAYS)))
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
            "speeds": [10, 20, 30, 45, 60], "tts": "azure_speech" if tts.configured() else "browser",
            "voices": {k: v[1] for k, v in tts.VOICES.items()}, "mcp": "/mcp/"}


class Decision(BaseModel):
    ref: str = Field(..., max_length=40, description="commentary id or moment id")
    decision: str = Field(..., pattern="^(approve|reject)$")
    text: str | None = Field(None, max_length=1200)
    producer: str = Field("producer", max_length=40)


@app.post("/api/replays/{rid}/decisions", status_code=201)
def producer_decision(rid: str, d: Decision):
    """Producer approval mode: record a human approve/reject of an LLM line in the audit log."""
    r = _replay(rid)
    rec = {"ts": round(time.time(), 3), "ref": d.ref, "task": "producer", "writer": d.producer,
           "verdict": d.decision, "text": d.text}
    r.audit.append(rec)
    return rec


@app.get("/api/replays/{rid}/audit")
def audit_log(rid: str, limit: int = Query(500, ge=1, le=5000)):
    """Audit log: every Verifier verdict (with evidence/problems) and every producer decision, oldest first."""
    r = _replay(rid)
    v = [a for a in r.audit if a["task"] != "producer"]
    return {"replay_id": rid, "entries": r.audit[-limit:], "total": len(r.audit),
            "summary": {"verifier_checks": len(v), "verifier_rejects": sum(a["verdict"] == "reject" for a in v),
                        "producer_approved": sum(a["verdict"] == "approve" for a in r.audit),
                        "producer_rejected": sum(a["verdict"] == "reject" and a["task"] == "producer" for a in r.audit)}}


class VerifyRequest(BaseModel):
    match_id: str
    text: str = Field(..., max_length=1200)
    minute: int | None = Field(None, ge=0, le=130)
    event_id: str | None = None


@app.post("/api/verify")
def verify(req: VerifyRequest, request: Request):
    VERIFY_RL.check(request)
    """Fact-check any line against the match (same Verifier as the live pipeline and the MCP tool)."""
    from echo_mcp.server import verify_commentary
    try:
        return verify_commentary(req.match_id, req.text, req.minute, req.event_id)
    except ValueError as ex:
        raise HTTPException(404, str(ex))


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=tts.MAX_CHARS)
    lang: str = Field("en", pattern="^(en|ar|es|fr|pt)$")
    voice: str | None = Field(None, max_length=40, description="optional alternative voice, e.g. ar-JO-TaimNeural")


@app.post("/api/tts")
async def speak(req: TTSRequest, request: Request):
    """Azure AI Speech neural voice (mp3). 503 when Speech is not configured: the UI then uses the browser voice."""
    TTS_RL.check(request)
    if not tts.configured():
        raise HTTPException(503, "Azure Speech not configured")
    try:
        audio = await tts.synthesize(req.text, req.lang, req.voice)
    except Exception as ex:  # noqa: BLE001 - quota / network: tell the UI to fall back
        raise HTTPException(502, f"speech failed: {type(ex).__name__}")
    return Response(audio, media_type="audio/mpeg", headers={"X-Voice": tts.pick(req.lang, req.voice)[1], "Cache-Control": "no-store"})


@app.get("/api/replays/{rid}/stream")
async def replay_stream(request: Request, rid: str, stats_every: int = Query(25, ge=1, le=500),
                        persona: str = Query("fan", pattern="^(fan|analyst)$"),
                        lang: str = Query("en", pattern="^(en|ar|es|fr|pt)$"),
                        club: str | None = Query(None, pattern="^(home|away)$"),
                        player: str | None = None, from_now: bool = False, agents: bool = True,
                        approval: bool = False):
    """SSE stream for one viewer.

    Events: `meta`, `match_event` (raw), `commentary`, `moment_card`, `overlay`, `stats`, `agent_trace`,
    `recap`, `end`. Persona/lang/club/player personalise the agent output; `from_now=true` joins the replay
    at its current position (used when the viewer changes preferences mid-match).
    """
    r = _replay(rid)
    settings = Settings.from_env()
    held, limited = False, None
    if agents and settings.mode == "foundry":
        held, limited = BUDGET.acquire(client_id(request.headers, request.client.host if request.client else None))
        if not held:
            from dataclasses import replace
            settings = replace(settings, mode="offline")

    async def gen():
        sent = r.position() if from_now else sum(1 for t in r.t if t < r.offset)
        orch = MatchOrchestrator(r.meta, Prefs(persona, lang, club, player), settings, approval=approval,
                                 audit=r.audit) if agents else None
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
        if orch:
            yield _sse("verifier", dict(orch.verify_stats))
        if orch and orch.uses_llm:
            yield _sse("usage", orch.usage())
        yield _sse("end", {"final_score": r.meta["final_score"]})

    async def guarded():
        try:
            if limited:
                yield _sse("notice", {"llm": "offline", "reason": limited})
            async for chunk in gen():
                yield chunk
        finally:
            if held:
                BUDGET.release()

    return StreamingResponse(guarded(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}
BUILD = os.environ.get("APP_BUILD") or str(int(max((p.stat().st_mtime for p in WEB_DIR.glob("*.*")), default=0)))


@app.get("/")
def index():
    """index.html with versioned asset URLs, so a browser never pairs a new page with an old cached app.js."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for f in ("app.js", "style.css"):
        html = html.replace(f'/static/{f}"', f'/static/{f}?v={BUILD}"')
    return HTMLResponse(html, headers=NO_CACHE)


@app.middleware("http")
async def no_cache_static(request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if not request.url.path.startswith(("/mcp", "/docs", "/redoc")):
        resp.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; media-src 'self' blob: data:; "
                                "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
    return resp


app.mount("/mcp", _MCP_APP)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
