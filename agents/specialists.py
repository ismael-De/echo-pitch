"""The four specialist agents. Each has a `primary` path (Foundry LLM, or the rich template when offline)
and a `safe` path (minimal deterministic text) used by the orchestrator after retries are exhausted."""
from __future__ import annotations

import json
import math
from typing import Any

import analytics as A

from . import templates as T


def _fmt_xg(x: float | None) -> str:
    return f"{(x or 0):.2f}"


def _audience(ctx: dict) -> str:
    return (f"Language: {ctx['lang']}. Audience: {ctx['persona']}. Favourite club: {ctx.get('club_name') or 'none'}. "
            f"Favourite player: {ctx.get('player_name') or 'none'}.")


AR_STYLE = (" Write the answer in Arabic, in the voice of a live Arab TV football commentator "
            "(think beIN Sports): fluent, modern standard Arabic that sounds spoken, short punchy sentences, "
            "natural football vocabulary (e.g. هدف، تسديدة، تصدٍّ، هجمة مرتدة، الشباك، القائم). "
            "Do not translate English idioms word for word. Keep player and club names in Latin script, "
            "use Western digits for numbers and scores, and never mix English words into the Arabic text.")

STYLE = {
    "en": " Write the answer in English.",
    "ar": AR_STYLE,
    "es": (" Write the answer in Spanish, like a lively Spanish-language TV football commentator: natural, idiomatic "
           "football Spanish (gol, disparo, parada, contraataque), no English words. Keep player and club names exactly as given."),
    "fr": (" Write the answer in French, like a French TV football commentator: natural, idiomatic football French "
           "(but, frappe, arrêt, contre-attaque), no English words. Keep player and club names exactly as given."),
    "pt": (" Write the answer in Brazilian Portuguese, like a Brazilian TV football narrator: natural, idiomatic "
           "(gol, chute, defesa, contra-ataque), no English words. Keep player and club names exactly as given."),
}


class Base:
    name = "base"

    def __init__(self, llm_agent: Any | None = None):
        self.llm = llm_agent

    async def _llm(self, prompt: str, lang: str = "en", agent: Any | None = None) -> str:
        from .foundry import run_text
        suffix = STYLE.get(lang, STYLE["en"])
        text = await run_text(agent or self.llm, prompt + suffix)
        check_language(text, lang)
        return text


# ---------------------------------------------------------------- Stats
class StatsAgent(Base):
    """Owns the deterministic numbers; exposes analytics functions as Agent Framework tools."""
    name = "stats"

    def snapshot(self, events: list[dict], meta: dict) -> dict:
        return A.match_state(events, meta)

    async def insight(self, st: dict, ctx: dict, llm: bool = True) -> str:
        if llm and self.llm:
            return await self._llm(f"{_audience(ctx)} Current clock {st['clock']}. "
                                   "Call get_live_stats and give one insight sentence.", ctx["lang"])
        return self.insight_template(st, ctx)

    def insight_template(self, st: dict, ctx: dict) -> str:
        lang, persona = ctx["lang"], ctx["persona"]
        pos = st["possession_pct"]
        dom_side = "home" if pos["home"] >= pos["away"] else "away"
        cvc = st["control_vs_chaos"][-1]["label"] if st["control_vs_chaos"] else "contested"
        vals = dict(clock=st["clock"], pos_h=pos["home"], pos_a=pos["away"], xg_h=st["xg"]["home"], xg_a=st["xg"]["away"],
                    sh_h=st["shots"]["home"], sh_a=st["shots"]["away"], dom=st["teams"][dom_side], pos=pos[dom_side],
                    phase=T.MOMENTS[lang]["phase"][cvc])
        return T.pick(T.LINES[lang]["insight"][persona], st["clock"]).format(**vals)

    def safe(self, st: dict, ctx: dict) -> str:
        return f"{st['clock']} {st['score']['home']}-{st['score']['away']} | xG {st['xg']['home']}-{st['xg']['away']}"


# ---------------------------------------------------------------- Moments
class MomentsAgent(Base):
    """Explains why a moment matters using game state, xG, momentum and control-vs-chaos context."""
    name = "moments"

    async def explain(self, moment: dict, ctx: dict, llm: bool = True) -> str:
        if llm and self.llm:
            return await self._llm(f"{_audience(ctx)} Moment: {json.dumps(moment_facts(moment), ensure_ascii=False)}", ctx["lang"])
        return self.explain_template(moment, ctx)

    def explain_template(self, m: dict, ctx: dict) -> str:
        L = T.MOMENTS[ctx["lang"]]
        c = m.get("context", {})
        team, opp = c.get("team_name", ""), c.get("opp_name", "")
        xg = m.get("xg") or m.get("xg_prevented") or 0.0
        v = dict(team=team, opp=opp, player=m.get("player"), xg=_fmt_xg(xg), pct=round(xg * 100),
                 minute=m["minute"] + 1, margin=abs(c.get("margin", 0)))
        if m["kind"] == "goal":
            mg = c.get("margin", 0)
            key = ("goal_equaliser" if mg == 0 else "goal_lead" if mg == 1 and c.get("was_level") else
                   "goal_extend" if mg == 2 else "goal_extend_more" if mg > 2 else "goal_pullback" if mg < 0 else "goal_lead")
            txt = L[key]
            mom = c.get("momentum_for_team", 0.0)
            if m["minute"] >= 80:
                txt += L["late"]
            if mom < -0.25:
                txt += L["against_run"]
            elif mom > 0.25:
                txt += L["with_run"]
            txt += L["low_xg"] if xg < 0.12 else (L["high_xg"] if xg > 0.35 else "")
            return txt.format(**v)
        if m["kind"] == "big_chance_missed":
            return L["big_chance"].format(**v)
        if m["kind"] == "key_save":
            return (L["key_save"] + (L["wonder"] if c.get("wonder") else "")).format(**v)
        if m["kind"] == "pressure_spike":
            v.update(value=c.get("value"), avg=c.get("avg"), turnovers=c.get("turnovers", 0),
                     phase=L["phase"][c.get("phase", "contested")])
            return L["pressure_spike"].format(**v)
        return m.get("reason", "")

    def safe(self, m: dict, ctx: dict) -> str:
        """Minimal localized line: title, player/team and the key number."""
        xg = m.get("xg") or m.get("xg_prevented")
        who = m.get("player") or m.get("context", {}).get("team_name", "")
        tail = f" ({xg:.2f} xG)" if xg else ""
        return f"{self.title(m, ctx['lang'])}: {who}{tail}."

    def title(self, m: dict, lang: str) -> str:
        return T.MOMENTS[lang]["titles"].get(m["kind"], m["kind"])


# ---------------------------------------------------------------- Narrator
class NarratorAgent(Base):
    """Live commentary lines and the full-time recap, in English or Arabic (two Agent instances: line + recap)."""
    name = "narrator"

    def __init__(self, llm_agent: Any | None = None, recap_agent: Any | None = None):
        super().__init__(llm_agent)
        self.recap_llm = recap_agent or llm_agent

    async def line(self, key: str, vals: dict, ctx: dict, llm: bool = True, facts: dict | None = None) -> str:
        if llm and self.llm:
            f = facts or {k: v for k, v in vals.items() if k not in ("event_id",)}
            return await self._llm(f"{_audience(ctx)} Event: {json.dumps(f, ensure_ascii=False)}", ctx["lang"])
        return self.line_template(key, vals, ctx)

    def line_template(self, key: str, vals: dict, ctx: dict) -> str:
        opts = T.LINES[ctx["lang"]][key][ctx["persona"]]
        return T.pick(opts, vals.get("event_id", key)).format(**vals)

    def safe_line(self, key: str, vals: dict, ctx: dict) -> str:
        kind = T.TYPE_NAMES[ctx["lang"]].get(vals.get("type", ""), key)
        return T.SAFE[ctx["lang"]].format(clock=vals.get("clock", ""), player=vals.get("player", ""),
                                          team=vals.get("team", ""), kind=kind)

    async def recap(self, st: dict, meta: dict, ctx: dict, llm: bool = True) -> str:
        if llm and self.llm:
            slim = {k: st[k] for k in ("score", "xg", "possession_pct", "shots")}
            slim["key_moments"] = [{k: m.get(k) for k in ("clock", "kind", "team", "player", "xg", "xg_prevented")}
                                   for m in st["key_moments"] if m["kind"] != "pressure_spike"][:10]
            slim["player_of_match"] = ctx.get("potm")
            slim["teams"] = {"home": meta["home"]["name"], "away": meta["away"]["name"]}
            return await self._recap_llm(ctx["lang"], f"{_audience(ctx)} Write the full-time recap. "
                                   f"Teams: {meta['home']['name']} (home) v {meta['away']['name']} (away), venue "
                                   f"{meta['venue']}. Stats: {json.dumps(slim, ensure_ascii=False)}")
        return self.recap_template(st, meta, ctx)

    async def _recap_llm(self, lang: str, prompt: str) -> str:
        return await self._llm(prompt, lang, agent=self.recap_llm)

    def recap_template(self, st: dict, meta: dict, ctx: dict) -> str:
        R = T.RECAP[ctx["lang"]]
        h, a = meta["home"]["name"], meta["away"]["name"]
        sc, xg, pos = st["score"], st["xg"], st["possession_pct"]
        score = f"{sc['home']}-{sc['away']}"
        if sc["home"] == sc["away"]:
            txt = R["result_draw"].format(home=h, away=a, score=score, venue=meta["venue"])
        else:
            w, l = (h, a) if sc["home"] > sc["away"] else (a, h)
            txt = R["result_win"].format(winner=w, loser=l, score=f"{max(sc.values())}-{min(sc.values())}", venue=meta["venue"])
        diff_goals, diff_xg = sc["home"] - sc["away"], xg["home"] - xg["away"]
        if abs(diff_xg) > 0.6 and (diff_goals == 0 or (diff_goals > 0) != (diff_xg > 0)):
            txt += R["xg_unfair"].format(xg_h=xg["home"], xg_a=xg["away"], better=h if diff_xg > 0 else a)
        else:
            txt += R["xg_fair"].format(xg_h=xg["home"], xg_a=xg["away"])
        goals = [m for m in st["key_moments"] if m["kind"] == "goal"]
        txt += R["goals"].format(goals=", ".join(f"{g['player']} {g['clock']}" for g in goals)) if goals else R["no_goals"]
        dom = "home" if pos["home"] >= pos["away"] else "away"
        txt += R["control"].format(dom=meta[dom]["name"], pos=pos[dom], comp=st["passing"][dom]["completion_pct"])
        saves = [m for m in st["key_moments"] if m["kind"] == "key_save"]
        if saves:
            s = max(saves, key=lambda m: m["xg_prevented"])
            txt += R["save"].format(keeper=s["player"], xg=_fmt_xg(s["xg_prevented"]), minute=s["minute"] + 1)
        potm = ctx.get("potm")
        if potm:
            txt += R["potm"].format(player=potm["player"], team=potm["team"])
        return txt

    def safe_recap(self, st: dict, meta: dict, ctx: dict) -> str:
        return f"{meta['home']['name']} {st['score']['home']}-{st['score']['away']} {meta['away']['name']}"


# ---------------------------------------------------------------- Persona
class PersonaAgent(Base):
    """Shapes output for the viewer: analyst vs fan, favourite club and favourite player."""
    name = "persona"

    async def shape(self, text: str, info: dict, ctx: dict, llm: bool = True) -> str:
        if llm and self.llm and info.get("important"):
            return await self._llm(f"{_audience(ctx)} Text: {text}", ctx["lang"])
        return self.shape_template(text, info, ctx)

    def shape_template(self, text: str, info: dict, ctx: dict) -> str:
        F = T.FAVOURITE[ctx["lang"]]
        if ctx.get("player_id") and info.get("player_id") == ctx["player_id"]:
            text = F["star"].format(player="") .strip() + " " + text
        club = ctx.get("club")
        if club and ctx["persona"] == "fan" and info.get("cheer") and info.get("team"):
            side = "for" if info["team"] == club else "against"
            text += " " + T.pick(F[side], info.get("event_id", "x")).format(club=ctx["club_name"])
        return text

    def safe(self, text: str, info: dict, ctx: dict) -> str:
        return text

    def overlay_kinds(self, ctx: dict) -> set[str]:
        base = {"goal_banner", "moment_card"}
        if ctx["persona"] == "analyst":
            return base | {"shot_xg", "pass_difficulty", "stat_bar", "player_tag"}
        return base | {"player_tag", "speed_alert", "stat_bar"}


def dist_to_goal(e: dict) -> float:
    gx = 105.0 if e["team"] == "home" else 0.0
    return math.hypot(gx - e["x"], 34 - e["y"])


class WrongLanguage(ValueError):
    pass


_STOP = {
    "en": {"the", "and", "with", "is", "his", "from", "after", "into", "their", "this", "for", "has", "was", "it's"},
    "es": {"el", "los", "las", "del", "con", "una", "por", "pero", "y", "su", "es", "muy", "para", "está"},
    "fr": {"le", "les", "des", "du", "avec", "une", "et", "est", "pour", "dans", "sur", "qui", "pas", "c'est"},
    "pt": {"o", "os", "do", "da", "dos", "com", "uma", "e", "não", "para", "pelo", "na", "no", "está"},
}


def check_language(text: str, lang: str) -> None:
    """Reject replies in the wrong language so the orchestrator retries (or keeps the template).

    Arabic is checked by script share; Latin-script languages by distinctive function words
    (player and club names are Latin in every language, so script alone cannot tell them apart)."""
    import re as _re
    arabic = len(_re.findall(r"[\u0600-\u06FF]", text))
    letters = len(_re.findall(r"[A-Za-z\u00C0-\u00FF\u0600-\u06FF]", text)) or 1
    if lang == "ar":
        if arabic / letters < 0.4:
            raise WrongLanguage("expected Arabic output")
        return
    if arabic > 0:
        raise WrongLanguage(f"expected {lang} output, got Arabic script")
    words = _re.findall(r"[a-zà-ÿ']+", text.lower())
    score = {k: sum(w in v for w in words) for k, v in _STOP.items()}
    best = max(score, key=lambda k: score[k])
    if lang in score and best != lang and score[best] >= 2 and score[best] > score[lang]:
        raise WrongLanguage(f"expected {lang} output, looks like {best}")


def moment_facts(m: dict) -> dict:
    """Unambiguous, name-based facts for the LLM (no home/away keys, no internal scores)."""
    c = m.get("context", {})
    team, opp = c.get("team_name"), c.get("opp_name")
    mom = c.get("momentum_for_team", 0.0)
    run = "with the run of play" if mom > 0.25 else ("against the run of play" if mom < -0.25 else "in an even spell")
    mg = c.get("margin", 0)
    state = f"{team} lead by {mg}" if mg > 0 else (f"{team} trail by {-mg}" if mg < 0 else "level")
    f = {"clock": m.get("clock"), "kind": m["kind"], "player": m.get("player"), "player_team": team, "opponent": opp,
         "game_state_after": state, "run_of_play_before": run}
    if m["kind"] == "goal":
        f.update(scorer=m.get("player"), scoring_team=team, xg=m.get("xg"), score_line=c.get("score_line"))
    elif m["kind"] == "big_chance_missed":
        f.update(missed_by=m.get("player"), xg=m.get("xg"))
    elif m["kind"] == "key_save":
        f.update(goalkeeper=m.get("player"), goalkeeper_team=team, denied_team=opp,
                 xg_prevented=m.get("xg_prevented"), world_class=bool(c.get("wonder")))
    elif m["kind"] == "pressure_spike":
        f.update(pressing_team=team, pressing_index=c.get("value"), match_average=c.get("avg"),
                 turnovers_in_window=c.get("turnovers"), phase=c.get("phase"))
        f.pop("player", None)
    return f
