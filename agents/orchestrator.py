"""Orchestrator: shared match state + handoffs Stats -> Moments -> Narrator -> Persona -> Render.

Each specialist call goes through `_invoke`, which applies a timeout, retries, and finally a deterministic
safe fallback, emitting an `agent_trace` record so the UI can show the agent pipeline working (or recovering).
Output items are `(sse_event_name, payload)` tuples: commentary, moment_card, overlay, stats, agent_trace, recap.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import analytics as A

from .config import Settings
from .specialists import MomentsAgent, NarratorAgent, PersonaAgent, StatsAgent, dist_to_goal

Item = tuple[str, dict]


@dataclass
class Prefs:
    persona: str = "fan"          # fan | analyst
    lang: str = "en"              # en | ar
    club: str | None = None       # "home" | "away" | None
    player_id: str | None = None

    def __post_init__(self):
        self.persona = self.persona if self.persona in ("fan", "analyst") else "fan"
        self.lang = self.lang if self.lang in ("en", "ar") else "en"
        self.club = self.club if self.club in ("home", "away") else None


class AgentFailure(RuntimeError):
    pass


class MatchOrchestrator:
    ROUTINE_GAP_S = 40           # min match seconds between routine commentary lines
    INSIGHT_EVERY_MIN = 10
    STATS_EVERY = 25

    def __init__(self, meta: dict, prefs: Prefs | None = None, settings: Settings | None = None,
                 llm_agents: dict | None = None):
        self.meta, self.prefs = meta, prefs or Prefs()
        self.settings = settings or Settings.from_env()
        if self.settings.mode == "foundry" and llm_agents is None:
            from .foundry import build_agents
            llm_agents = build_agents(self.settings, self._stats_tools())
        llm_agents = llm_agents or {}
        self.stats = StatsAgent(llm_agents.get("stats"))
        self.moments = MomentsAgent(llm_agents.get("moments"))
        self.narrator = NarratorAgent(llm_agents.get("narrator"), llm_agents.get("recap"))
        self.persona = PersonaAgent(llm_agents.get("persona"))
        # ---- shared match state (the blackboard all agents read/write) ----
        self.events: list[dict] = []
        self.score = {"home": 0, "away": 0}
        self.fouls = {"home": 0, "away": 0}
        self.moment_log: list[dict] = []
        self.trace: list[dict] = []
        self.last_routine_t = -999
        self.last_insight_min = 0
        self.last_window: tuple[int, int] = (1, 0)
        self._faulted: set[str] = set()
        self._bg: set[asyncio.Task] = set()   # in-flight LLM upgrades (never block the replay)
        self._ready: list[Item] = []          # finished upgrades waiting to be streamed
        self._cid = 0
        self._ov = 0
        p = self.prefs
        lineup = {pl["player_id"]: pl for s in ("home", "away") for pl in meta[s]["lineup"]}
        self.ctx = {"lang": p.lang, "persona": p.persona, "club": p.club,
                    "club_name": meta[p.club]["name"] if p.club else None, "player_id": p.player_id,
                    "player_name": lineup.get(p.player_id, {}).get("name")}
        self.overlay_kinds = self.persona.overlay_kinds(self.ctx)

    # ------------------------------------------------------------ tools for the Foundry Stats agent
    def _stats_tools(self) -> list[Callable[..., Any]]:
        def get_live_stats() -> dict:
            """Current score, possession, shots, xG, passing and momentum for the live match."""
            st = A.match_state(self.events, self.meta)
            names = {s_: self.meta[s_]["name"] for s_ in ("home", "away")}
            by_name = lambda d: {names[k]: v for k, v in d.items()}
            return {"clock": st["clock"], "score": by_name(st["score"]), "possession_pct": by_name(st["possession_pct"]),
                    "shots": by_name(st["shots"]), "xg": by_name(st["xg"]),
                    "pass_completion_pct": {names[k]: v["completion_pct"] for k, v in st["passing"].items()},
                    "team_on_top_now": (names["home"] if st["momentum_now"] > 0.15 else
                                        names["away"] if st["momentum_now"] < -0.15 else "neither"),
                    "phase": st["control_vs_chaos"][-1]["label"] if st["control_vs_chaos"] else None}

        def get_key_moments() -> list:
            """Key moments so far (goals, big chances, saves, pressure spikes) with importance and reasons."""
            return A.key_moments(self.events)

        def get_explainability() -> dict:
            """Control-vs-chaos phases, pressure shifts and rhythm for the match so far."""
            return {"control_vs_chaos": A.control_vs_chaos(self.events), "pressure_shifts": A.pressure_shifts(self.events),
                    "rhythm": A.rhythm(self.events)}
        return [get_live_stats, get_key_moments, get_explainability]

    # ------------------------------------------------------------ resilient invocation
    async def _invoke(self, agent: str, task: str, primary: Callable[[], Awaitable[str]],
                      safe: Callable[[], str], out: list[Item], traced: bool = True,
                      source: str | None = None) -> tuple[str, str]:
        s = self.settings
        t0, attempts, err = time.perf_counter(), 0, None
        for attempt in range(s.retries + 1):
            attempts += 1
            try:
                if agent in s.fault_always or (agent in s.fault_once and agent not in self._faulted):
                    self._faulted.add(agent)
                    raise AgentFailure(f"injected fault in {agent}")
                text = await asyncio.wait_for(primary(), timeout=s.timeout_s)
                status = "ok" if attempt == 0 else "recovered"
                source = source or ("llm" if getattr(self, agent).llm else "template")
                break
            except Exception as ex:  # noqa: BLE001 - any agent failure triggers retry/fallback
                err = f"{type(ex).__name__}: {ex}"
        else:
            text, status, source = safe(), "fallback", "safe_template"
        if traced or status != "ok":
            rec = {"agent": agent, "task": task, "status": status, "attempts": attempts, "source": source,
                   "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "error": err if status != "ok" else None,
                   "clock": A.match_clock(self.events[-1]) if self.events else "0'"}
            self.trace.append(rec)
            out.append(("agent_trace", rec))
        return text, source

    # ------------------------------------------------------------ async LLM upgrades
    @property
    def uses_llm(self) -> bool:
        return any(a.llm is not None for a in (self.stats, self.moments, self.narrator, self.persona))

    def _spawn(self, coro) -> None:
        """Run an LLM upgrade in the background; its results are collected by `drain()`."""
        task = asyncio.ensure_future(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)

    def drain(self) -> list[Item]:
        """Return (and clear) upgrade items produced by finished background LLM calls."""
        out, self._ready = self._ready, []
        return out

    async def flush(self, timeout: float | None = None) -> list[Item]:
        """Wait for in-flight upgrades (bounded) and return everything ready."""
        if self._bg:
            await asyncio.wait(list(self._bg), timeout=timeout or self.settings.timeout_s * (self.settings.retries + 1))
        return self.drain()

    def _facts(self, key: str, v: dict, e: dict | None) -> dict:
        """Curated, name-based facts for one commentary line (keeps the LLM from mixing up teams or numbers)."""
        sl = f"{self.meta['home']['name']} {self.score['home']}-{self.score['away']} {self.meta['away']['name']}"
        f = {"clock": v.get("clock"), "kind": key, "score_line": sl}
        if e is None:
            f.update({k: v[k] for k in ("xg_h", "xg_a", "pos_h", "pos_a") if k in v},
                     home_team=self.meta["home"]["name"], away_team=self.meta["away"]["name"])
            return f
        if key == "goal" or key.startswith("shot"):
            f.update(shooter=v["player"], shooter_team=v["team"], opponent=v["opp"], xg=v["xg"],
                     distance_m=v["dist"], shot_speed_kmh=v["speed"])
        elif key in ("save", "save_wonder"):
            f.update(goalkeeper=v["player"], goalkeeper_team=v["team"], shooter=v.get("shooter"),
                     shooter_team=v["opp"], xg_faced=v["xg"], distance_m=v.get("shot_dist"))
        else:
            f.update(player=v["player"], team=v["team"], zone=v["zone"])
        return f

    async def _upgrade_comment(self, cid: str, key: str, vals: dict, info: dict, facts: dict | None = None) -> None:
        out: list[Item] = []
        text, src = await self._invoke("narrator", key, lambda: self.narrator.line(key, vals, self.ctx, facts=facts),
                                       lambda: "", out)
        if src == "llm" and text:
            text = await self._persona_pass(text, info, out)
            out.append(("commentary_update", {"id": cid, "text": text, "source": "llm"}))
        self._ready.extend(out)

    async def _upgrade_moment(self, card: dict, m: dict, info: dict) -> None:
        out: list[Item] = []
        expl, src = await self._invoke("moments", m["kind"], lambda: self.moments.explain(m, self.ctx),
                                       lambda: "", out)
        if src == "llm" and expl:
            expl = await self._persona_pass(expl, info, out)
            card.update(why=expl, source="llm", update=True)
            out.append(("moment_card", dict(card)))
        self._ready.extend(out)

    async def _upgrade_insight(self, cid: str, st: dict) -> None:
        out: list[Item] = []
        text, src = await self._invoke("stats", "insight", lambda: self.stats.insight(st, self.ctx), lambda: "", out)
        if src == "llm" and text:
            out.append(("commentary_update", {"id": cid, "text": text, "source": "llm"}))
        self._ready.extend(out)

    async def _persona_pass(self, text: str, info: dict, out: list[Item]) -> str:
        """Persona context is already in the Narrator/Moments prompts; by default only the deterministic
        favourite-player marker is applied (no extra LLM call). LLM_PERSONA_REWRITE=1 adds a Persona LLM pass."""
        if self.settings.persona_rewrite and self.persona.llm is not None:
            text, _ = await self._invoke("persona", "rewrite", lambda: self.persona.shape(text, info, self.ctx),
                                         lambda: text, out)
            return text
        return self.persona.shape_template(text, {**info, "cheer": False}, self.ctx)

    def usage(self) -> dict:
        """Token usage per agent for this stream (Foundry mode)."""
        out = {}
        for n in ("stats", "moments", "narrator", "persona", "recap"):
            a = self.narrator.recap_llm if n == "recap" else getattr(self, n).llm
            if a is not None and getattr(a, "echo_usage", None):
                out[n] = dict(a.echo_usage)
        return out

    def _next_cid(self) -> str:
        self._cid += 1
        return f"c-{self._cid:05d}"

    # ------------------------------------------------------------ helpers
    def _overlay(self, out: list[Item], kind: str, e: dict | None, duration: float, payload: dict, anchor: str):
        if kind not in self.overlay_kinds:
            return
        self._ov += 1
        start = (e["minute"] * 60 + e["second"]) if e else 0
        out.append(("overlay", {"overlay_id": f"ov-{self._ov:05d}", "kind": kind, "anchor": anchor,
                                "start_s": start, "duration_s": duration, "clock": A.match_clock(e) if e else "0'",
                                "lang": self.prefs.lang, "payload": payload}))

    def _vals(self, e: dict) -> dict:
        side = e["team"]
        opp = "away" if side == "home" else "home"
        ax = e["x"] if side == "home" else 105 - e["x"]
        zones = {"en": ("defensive third", "midfield", "final third"), "ar": ("الثلث الدفاعي", "وسط الملعب", "الثلث الأخير")}
        zone = zones[self.prefs.lang][0 if ax < 35 else 1 if ax < 70 else 2]
        length = 0
        if e.get("end_x") is not None:
            length = round(((e["end_x"] - e["x"]) ** 2 + (e["end_y"] - e["y"]) ** 2) ** 0.5)
        h, a = self.meta["home"]["code"], self.meta["away"]["code"]
        return {"event_id": e["event_id"], "type": e["type"], "clock": A.match_clock(e), "player": e["player_name"],
                "team": self.meta[side]["name"], "opp": self.meta[opp]["name"],
                "score": f"{h} {self.score['home']}-{self.score['away']} {a}",
                "xg": f"{(e.get('xg') or 0):.2f}", "dist": round(dist_to_goal(e)),
                "speed": round(e["speed_kmh"] or 0), "press": f"{e['pressure_level']:.2f}", "zone": zone,
                "length": length, "fouls": self.fouls[side],
                "diff": A.pass_difficulty(e) if e["type"] == "pass" else 0}

    async def _comment(self, out, key, e, vals, important=False, cheer=False):
        """Template line immediately (never blocks the replay); key lines get an async LLM upgrade."""
        info = {"player_id": e["player_id"] if e else None, "team": e["team"] if e else None, "important": important,
                "event_id": vals.get("event_id", key), "cheer": cheer}
        upgrade = important and self.narrator.llm is not None
        text, src = await self._invoke("narrator", key, lambda: self.narrator.line(key, vals, self.ctx, llm=False),
                                       lambda: self.narrator.safe_line(key, vals, self.ctx), out,
                                       traced=important and not upgrade, source="template")
        text, _ = await self._invoke("persona", "shape", lambda: self.persona.shape(text, info, self.ctx, llm=False),
                                     lambda: self.persona.safe(text, info, self.ctx), out,
                                     traced=important and not upgrade, source="template")
        cid = self._next_cid()
        out.append(("commentary", {"id": cid, "event_id": vals.get("event_id"), "clock": vals.get("clock", "0'"),
                                   "kind": key, "team": e["team"] if e else None, "text": text, "lang": self.prefs.lang,
                                   "persona": self.prefs.persona, "source": src, "important": important}))
        if upgrade and src != "safe_template":
            self._spawn(self._upgrade_comment(cid, key, vals, info, self._facts(key, vals, e)))

    def _state_snapshot(self) -> dict:
        return self.stats.snapshot(self.events, self.meta)

    def _game_state_ctx(self, side: str, kind: str, minute: int) -> dict:
        opp = "away" if side == "home" else "home"
        mom = A.momentum(self.events)
        m_before = mom[-2]["momentum"] if len(mom) > 1 else 0.0  # momentum just before this action
        return {"team_name": self.meta[side]["name"], "opp_name": self.meta[opp]["name"],
                "score_line": f"{self.meta['home']['name']} {self.score['home']}-{self.score['away']} {self.meta['away']['name']}",
                "margin": self.score[side] - self.score[opp],
                "momentum_for_team": m_before if side == "home" else -m_before}

    async def _moment(self, out: list[Item], m: dict, e: dict | None):
        """Handoff chain for a key moment: Stats (context) -> Moments (why) -> Persona (audience) -> card + overlay.
        The card is rendered at once from templates; with Foundry, an LLM-written `why` replaces it asynchronously."""
        upgrade = self.moments.llm is not None
        expl, src = await self._invoke("moments", m["kind"], lambda: self.moments.explain(m, self.ctx, llm=False),
                                       lambda: self.moments.safe(m, self.ctx), out, traced=not upgrade,
                                       source="template")
        info = {"player_id": e["player_id"] if e else None, "team": m.get("team"), "important": True,
                "event_id": m.get("event_id") or m["kind"], "cheer": m["kind"] != "pressure_spike"}
        expl, _ = await self._invoke("persona", "shape_moment", lambda: self.persona.shape(expl, info, self.ctx, llm=False),
                                     lambda: self.persona.safe(expl, info, self.ctx), out, traced=not upgrade,
                                     source="template")
        card = {"moment_id": f"m-{len(self.moment_log) + 1:03d}", "kind": m["kind"],
                "title": self.moments.title(m, self.prefs.lang), "clock": m["clock"], "minute": m["minute"],
                "team": m.get("team"), "player": m.get("player"), "importance": m.get("importance"),
                "why": expl, "source": src, "metrics": {k: m[k] for k in ("xg", "xg_prevented", "score_after") if k in m},
                "lang": self.prefs.lang}
        self.moment_log.append(card)
        out.append(("moment_card", dict(card)))
        self._overlay(out, "moment_card", e, 10, {"title": card["title"], "text": expl, "team": card["team"]}, "lower_third")
        if upgrade and src != "safe_template":
            self._spawn(self._upgrade_moment(card, m, info))

    # ------------------------------------------------------------ public API
    async def start(self) -> list[Item]:
        out: list[Item] = []
        vals = {"home": self.meta["home"]["name"], "away": self.meta["away"]["name"], "event_id": "kickoff"}
        await self._comment(out, "kickoff", None, vals)
        if self.settings.warning:
            out.append(("agent_trace", {"agent": "orchestrator", "task": "config", "status": "warning",
                                        "error": self.settings.warning}))
        return out

    async def on_event(self, e: dict) -> list[Item]:
        out: list[Item] = []
        if self.events and self.events[-1]["period"] == 1 and e["period"] == 2:
            out += await self._period_line("halftime")
        self.events.append(e)
        side, t = e["team"], e["minute"] * 60 + e["second"]
        vals = self._vals(e)
        fav = self.prefs.player_id and e["player_id"] == self.prefs.player_id
        if fav and e["type"] in ("pass", "carry", "shot", "tackle"):
            self._overlay(out, "player_tag", e, 3, {"player": e["player_name"], "player_id": e["player_id"],
                                                    "speed_kmh": e["speed_kmh"], "x": e["x"], "y": e["y"]}, "pitch")
        typ, outc = e["type"], e["outcome"]
        if typ == "goal":
            self.score[side] += 1
            shot = self.events[-2] if len(self.events) > 1 and self.events[-2]["type"] == "shot" else e
            vals = self._vals(shot)  # distance/speed come from the shot, score from the updated state
            await self._comment(out, "goal", e, vals, important=True, cheer=True)
            self._overlay(out, "goal_banner", e, 12, {"team": side, "player": e["player_name"], "score": dict(self.score),
                                                      "xg": e["xg"]}, "top")
            ctx = self._game_state_ctx(side, "goal", e["minute"])
            ctx["was_level"] = ctx["margin"] == 1
            await self._moment(out, {"kind": "goal", "event_id": e["event_id"], "minute": e["minute"], "clock": vals["clock"],
                                     "team": side, "player": e["player_name"], "xg": e["xg"],
                                     "importance": 1.0 if e["minute"] >= 80 else 0.9, "score_after": dict(self.score),
                                     "context": ctx}, e)
        elif typ == "shot" and outc != "goal":
            key = {"saved": "shot_saved", "blocked": "shot_blocked"}.get(outc, "shot_off_target")
            await self._comment(out, key, e, vals, important=e["xg"] >= 0.15)
            self._overlay(out, "shot_xg", e, 5, {"player": e["player_name"], "xg": e["xg"], "speed_kmh": e["speed_kmh"],
                                                 "outcome": outc, "team": side}, "top_right")
            if e["xg"] >= A.stats.BIG_CHANCE_XG and outc != "saved":
                await self._moment(out, {"kind": "big_chance_missed", "event_id": e["event_id"], "minute": e["minute"],
                                         "clock": vals["clock"], "team": side, "player": e["player_name"], "xg": e["xg"],
                                         "importance": round(0.5 + e["xg"] / 2, 2),
                                         "context": self._game_state_ctx(side, "chance", e["minute"])}, e)
        elif typ == "save":
            shot = self.events[-2] if len(self.events) > 1 else {}
            xg = shot.get("xg") or 0.0
            vals["xg"] = f"{xg:.2f}"
            if shot:
                vals.update(shooter=shot.get("player_name"), shot_dist=round(dist_to_goal(shot)))
            wonder = outc == "wonder_save"
            if wonder or xg >= 0.15:
                if wonder:  # routine saves are already covered by the shot line + moment card
                    await self._comment(out, "save_wonder", e, vals, important=True, cheer=True)
                ctx = self._game_state_ctx(side, "save", e["minute"])
                ctx["wonder"] = wonder
                await self._moment(out, {"kind": "key_save", "event_id": e["event_id"], "minute": e["minute"],
                                         "clock": vals["clock"], "team": side, "player": e["player_name"],
                                         "xg_prevented": xg, "importance": round(min(1.0, 0.55 + xg), 2),
                                         "context": ctx}, e)
        elif typ == "foul":
            self.fouls[side] += 1
            await self._routine(out, "foul", e, vals, t)
        elif typ == "tackle" and outc == "won":
            await self._routine(out, "tackle", e, vals, t, fav)
        elif typ == "pass" and outc == "complete" and vals["diff"] >= 65:
            self._overlay(out, "pass_difficulty", e, 4, {"player": e["player_name"], "difficulty": vals["diff"],
                                                         "length_m": vals["length"], "team": side}, "top_right")
            await self._routine(out, "hard_pass", e, vals, t, fav)
        elif typ == "carry" and (e["speed_kmh"] or 0) >= 27 and vals["length"] >= 10:
            self._overlay(out, "speed_alert", e, 4, {"player": e["player_name"], "speed_kmh": e["speed_kmh"],
                                                     "team": side}, "pitch")
            await self._routine(out, "speed", e, vals, t, fav)
        # windowed analytics: pressure spikes + periodic stats insight
        w = A.stats._bucket(e, 5)
        if w > self.last_window:
            self.last_window = w
            await self._pressure_check(out, e)
        if e["minute"] - self.last_insight_min >= self.INSIGHT_EVERY_MIN:
            self.last_insight_min = e["minute"]
            st = self._state_snapshot()
            text, src = await self._invoke("stats", "insight", lambda: self.stats.insight(st, self.ctx, llm=False),
                                           lambda: self.stats.safe(st, self.ctx), out, source="template")
            cid = self._next_cid()
            if self.stats.llm is not None and src != "safe_template":
                self._spawn(self._upgrade_insight(cid, st))
            out.append(("commentary", {"id": cid, "event_id": None, "clock": st["clock"], "kind": "insight", "team": None,
                                       "text": text, "lang": self.prefs.lang, "persona": self.prefs.persona,
                                       "source": src, "important": False}))
            self._overlay(out, "stat_bar", e, 10, {"possession": st["possession_pct"], "xg": st["xg"],
                                                   "shots": st["shots"]}, "lower_third")
        if len(self.events) % self.STATS_EVERY == 0:
            out.append(("stats", self.compact_stats()))
        out += self.drain()
        return out

    async def _routine(self, out, key, e, vals, t, force=False):
        if force or t - self.last_routine_t >= self.ROUTINE_GAP_S:
            self.last_routine_t = t
            await self._comment(out, key, e, vals)

    async def _pressure_check(self, out: list[Item], e: dict):
        pi = A.pressure_index(self.events, 5)
        done = pi[:-1]  # last window is still open
        if len(done) < 4:
            return
        last = done[-1]
        for s in ("home", "away"):
            hist = [r[s] for r in done[:-1]]
            mu = sum(hist) / len(hist)
            sd = (sum((v - mu) ** 2 for v in hist) / len(hist)) ** 0.5 or 1.0
            if last[s] >= mu + 1.5 * sd and last[s] >= 40:
                win = [x for x in self.events if A.stats._bucket(x, 5) == (last["period"], last["minute"])]
                cvc = A.control_vs_chaos(win)
                ctx = self._game_state_ctx(s, "pressure", e["minute"])
                ctx.update(value=last[s], avg=round(mu, 1), phase=cvc[0]["label"] if cvc else "contested",
                           turnovers=sum(x["type"] == "possession_change" for x in win))
                await self._moment(out, {"kind": "pressure_spike", "event_id": None, "minute": last["minute"],
                                         "clock": last["label"], "team": s, "player": None,
                                         "importance": 0.6, "reason": f"pressing index {last[s]} vs {mu:.1f}",
                                         "context": ctx}, None)

    async def _period_line(self, key: str) -> list[Item]:
        out: list[Item] = []
        st = self._state_snapshot()
        h, a = self.meta["home"]["code"], self.meta["away"]["code"]
        vals = {"event_id": key, "clock": st["clock"], "score": f"{h} {st['score']['home']}-{st['score']['away']} {a}",
                "xg_h": st["xg"]["home"], "xg_a": st["xg"]["away"], "pos_h": st["possession_pct"]["home"],
                "pos_a": st["possession_pct"]["away"]}
        await self._comment(out, key, None, vals, important=True)
        out.append(("stats", self.compact_stats(st)))
        return out

    def compact_stats(self, st: dict | None = None) -> dict:
        st = st or self._state_snapshot()
        keep = ("clock", "score", "possession_pct", "shots", "shots_on_target", "xg", "passing", "fouls",
                "momentum_now", "momentum", "events_processed")
        d = {k: st[k] for k in keep}
        d["phase"] = st["control_vs_chaos"][-1]["label"] if st["control_vs_chaos"] else None
        d["rhythm"] = st["rhythm"][-1]["label"] if st["rhythm"] else None
        return d

    def player_of_match(self, st: dict) -> dict | None:
        score: dict[str, float] = {}
        names: dict[str, tuple] = {}
        for e in self.events:
            pid = e["player_id"]
            names[pid] = (e["player_name"], self.meta[e["team"]]["name"])
            v = {"goal": 3.0, "save": 0.5}.get(e["type"], 0.0)
            if e["type"] == "shot":
                v += e["xg"]
            if e["type"] == "tackle" and e["outcome"] == "won":
                v += 0.3
            if e["type"] == "pass" and e["outcome"] == "complete" and A.pass_difficulty(e) >= 60:
                v += 0.1
            if e["outcome"] == "wonder_save":
                v += 1.5
            score[pid] = score.get(pid, 0) + v
        if not score:
            return None
        sc = self.score
        if sc["home"] != sc["away"]:  # small bonus for the winning side
            win = self.meta["home" if sc["home"] > sc["away"] else "away"]["name"]
            for p_ in score:
                if names[p_][1] == win:
                    score[p_] += 1.0
        pid = max(score, key=score.get)
        return {"player_id": pid, "player": names[pid][0], "team": names[pid][1], "score": round(score[pid], 2)}

    async def finish(self) -> list[Item]:
        out = await self.flush()
        out += await self._period_line("fulltime")
        st = self._state_snapshot()
        potm = self.player_of_match(st)
        ctx = {**self.ctx, "potm": potm}
        text, src = await self._invoke("narrator", "recap", lambda: self.narrator.recap(st, self.meta, ctx),
                                       lambda: self.narrator.safe_recap(st, self.meta, ctx), out)
        out.append(("recap", {"text": text, "lang": self.prefs.lang, "persona": self.prefs.persona, "source": src,
                              "score": st["score"], "xg": st["xg"], "possession_pct": st["possession_pct"],
                              "shots": st["shots"], "player_of_match": potm,
                              "moments": [{k: m[k] for k in ("clock", "kind", "title", "player", "team")}
                                          for m in self.moment_log]}))
        return out
