"""Measured evaluation of the Verifier (Guard) agent. Every number in docs/EVAL.md comes from this script.

  python scripts/eval_verifier.py                      # offline: template lines, all matches x 5 languages
  python scripts/eval_verifier.py --foundry --langs en ar es fr pt   # + real gpt-5-mini lines on Foundry

What it measures
  1. Clean pass rate: correct lines that the Verifier accepts (false rejections = 1 - this).
  2. Planted errors: each correct line is corrupted one way at a time (wrong number, wrong score pair,
     wrong roster player, invented player, swapped team) and we count how many corruptions still pass.
  3. Verifier latency per check.
  4. (--foundry) real LLM drafts: first-draft pass rate, rewrite outcome, unverified lines shown,
     LLM latency, and an LLM-as-judge groundedness score (1-5) of the lines that were shown.
Writes docs/eval_results.json.
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import MatchOrchestrator, Prefs, Settings  # noqa: E402
from agents import verifier as VM  # noqa: E402

RNG = random.Random(7)
INVENTED = "Marco Vellani"
CAPTURE: list[dict] = []
_orig_check = VM.Verifier.check


def _capturing_check(self, text, facts):
    t0 = time.perf_counter()
    v = _orig_check(self, text, facts)
    CAPTURE.append({"text": text, "facts": facts, "ok": v.ok, "problems": v.problems, "verifier": self,
                    "us": (time.perf_counter() - t0) * 1e6})
    return v


VM.Verifier.check = _capturing_check


def load(mp):
    meta = json.load(open(mp))
    ev = [json.loads(l) for l in open(mp.replace("_meta.json", "_events.jsonl")) if l.strip()]
    return meta, ev


async def replay(meta, ev, prefs, settings, flush=False):
    o = MatchOrchestrator(meta, prefs, settings)
    items = await o.start()
    for e in ev:
        items += await o.on_event(e)
        if flush and o._bg and e["type"] in ("goal", "shot", "save"):
            await asyncio.sleep(0)  # let background LLM upgrades progress
    items += await o.finish()
    return o, items


# ------------------------------------------------------------------ corruptions
def _all_numbers(facts):
    nums = set()
    for p, v in VM._walk(facts):
        for x, *_ in VM._numbers_of(p, v):
            nums.add(round(x, 2))
    return nums


def corruptions(rec):
    """Yield (kind, corrupted_text) pairs; each corruption makes exactly one claim false."""
    text, facts, V = rec["text"], rec["facts"], rec["verifier"]
    t = text.translate(VM._AR_DIGITS)
    nums = _all_numbers(facts)
    strings = " | ".join(str(v) for _, v in VM._walk(facts) if isinstance(v, str))
    pm = VM._PAIR.search(t)
    if pm:
        a, b = pm.group(1), pm.group(2)
        na = str(int(float(a)) + 1) if "." not in a else f"{float(a) + 0.4:.2f}"
        yield "wrong_score_pair", t[:pm.start(1)] + na + t[pm.end(1):]
    singles = [m for m in VM._NUM.finditer(t) if not (pm and pm.start() <= m.start() < pm.end())]
    if singles:
        m = RNG.choice(singles)
        x = float(m.group())
        for step in (7, 13, 19, 23, 29):
            y = round(x + (step if "." not in m.group() else step / 37), 2)
            if y not in nums:
                break
        rep = str(int(y)) if "." not in m.group() else f"{y:.2f}"
        yield "wrong_number", t[:m.start()] + rep + t[m.end():]
    present = [n for n in V.players if n in t and n in strings]
    if present:
        name = present[0]
        others = [p for p in V.players if p not in strings and p.split()[-1] not in strings]
        if others:
            yield "wrong_player", t.replace(name, RNG.choice(others))
        yield "invented_player", t.replace(name, INVENTED)
    teams = [n for n in V.teams if n in t]
    if len(teams) == 1:
        other = [n for n in V.teams if n != teams[0]][0]
        yield "swapped_team", t.replace(teams[0], other)


def score(records):
    clean = [r for r in records if r["text"]]
    out = {"lines": len(clean), "clean_pass": sum(r["ok"] for r in clean), "planted": {}, "examples_missed": []}
    for r in clean:
        if not r["ok"]:
            continue
        for kind, bad in corruptions(r):
            if bad == r["text"].translate(VM._AR_DIGITS):
                continue
            v = _orig_check(r["verifier"], bad, r["facts"])
            k = out["planted"].setdefault(kind, {"planted": 0, "caught": 0})
            k["planted"] += 1
            k["caught"] += (not v.ok)
            if v.ok and len(out["examples_missed"]) < 6:
                out["examples_missed"].append({"kind": kind, "text": bad})
    tot_p = sum(k["planted"] for k in out["planted"].values())
    tot_c = sum(k["caught"] for k in out["planted"].values())
    out["planted_total"], out["caught_total"] = tot_p, tot_c
    num_kinds = [k for k in out["planted"] if k != "swapped_team"]
    out["caught_excl_team_swap"] = [sum(out["planted"][k]["caught"] for k in num_kinds),
                                    sum(out["planted"][k]["planted"] for k in num_kinds)]
    us = sorted(r["us"] for r in clean)
    out["verifier_latency_us"] = {"p50": round(us[len(us) // 2], 1), "p95": round(us[int(len(us) * .95)], 1),
                                  "max": round(us[-1], 1)} if us else None
    return out


# ------------------------------------------------------------------ offline
async def offline():
    CAPTURE.clear()
    s = Settings()
    per_lang = {}
    for mp in sorted(glob.glob(str(ROOT / "data" / "*_meta.json"))):
        meta, ev = load(mp)
        for lang in ("en", "ar", "es", "fr", "pt", "ru"):
            for persona in ("fan", "analyst"):
                start = len(CAPTURE)
                await replay(meta, ev, Prefs(persona, lang, "home", meta["home"]["lineup"][9]["player_id"]), s)
                per_lang.setdefault(lang, []).extend(CAPTURE[start:])
    recs = [r for r in CAPTURE if r["text"]]
    res = score(recs)
    res["by_language"] = {lg: {"lines": len(v), "clean_pass": sum(r["ok"] for r in v)} for lg, v in per_lang.items()}
    return res


# ------------------------------------------------------------------ foundry
JUDGE = ("You are a strict fact-checking judge. Given FACTS (JSON) and a football commentary STATEMENT, rate how well "
         "every factual claim in the statement (numbers, names, who did what, score) is supported by the facts. "
         "Style, emotion and opinions are fine. Answer with one digit only: 5 = fully supported, 4 = minor "
         "unsupported detail, 3 = some unsupported claims, 2 = mostly unsupported, 1 = contradicts the facts.")


async def foundry(langs, match, limit_events):
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from agents.foundry import _credential, run_text
    s = Settings.from_env()
    if s.mode != "foundry":
        raise SystemExit("set LLM_MODE=foundry and FOUNDRY_PROJECT_ENDPOINT")
    meta, ev = load(str(ROOT / "data" / f"{match}_meta.json"))
    ev = ev[:limit_events] if limit_events else ev
    runs = []
    for lang in langs:
        CAPTURE.clear()
        t0 = time.perf_counter()
        o, items = await replay(meta, ev, Prefs("fan" if lang in ("en", "ar") else "analyst", lang), s, flush=True)
        wall = time.perf_counter() - t0
        llm_audit = [a for a in o.audit if a["writer"] == "llm"]
        drafts1 = [a for a in llm_audit if a["attempt"] == 1]
        drafts2 = [a for a in llm_audit if a["attempt"] == 2]
        shown = [d for k, d in items if k == "commentary_update"] + \
                [d for k, d in items if k == "moment_card" and d.get("update")] + \
                [d for k, d in items if k == "recap" and d["source"] == "llm"]
        shown_unverified = sum(1 for d in shown if not d.get("verified"))
        lat = sorted(t["latency_ms"] for t in o.trace if t.get("source") == "llm" and t["agent"] != "verifier")
        llm_recs = [r for r in CAPTURE if r["text"] in {a["text"] for a in llm_audit}]
        planted = score([r for r in llm_recs if r["ok"]])
        runs.append({"lang": lang, "wall_s": round(wall, 1), "llm_drafts": len(drafts1),
                     "first_draft_pass": sum(a["verdict"] == "pass" for a in drafts1),
                     "rewrites": len(drafts2), "rewrite_pass": sum(a["verdict"] == "pass" for a in drafts2),
                     "kept_template": o.verify_stats["fallbacks"], "llm_lines_shown": len(shown),
                     "shown_unverified": shown_unverified,
                     "rejections": [{"text": a["text"], "problems": a["problems"]} for a in llm_audit
                                    if a["verdict"] == "reject"][:8],
                     "llm_latency_ms": {"p50": lat[len(lat) // 2] if lat else None,
                                        "p95": lat[int(len(lat) * .95)] if lat else None, "n": len(lat)},
                     "planted_on_llm_lines": {k: planted[k] for k in ("planted", "planted_total", "caught_total",
                                                                       "caught_excl_team_swap")},
                     "shown_texts": [{"text": a["text"], "facts": next((r["facts"] for r in llm_recs
                                                                       if r["text"] == a["text"]), None)}
                                     for a in llm_audit if a["verdict"] == "pass"]})
    # LLM-as-judge groundedness of the lines that passed the Verifier and were shown
    client = FoundryChatClient(project_endpoint=s.project_endpoint, model=s.model, credential=_credential())
    judge = Agent(client=client, name="echo-judge", instructions=JUDGE,
                  default_options={"max_tokens": 300, "reasoning": {"effort": "minimal"}})
    for r in runs:
        scores = []
        for x in r.pop("shown_texts"):
            try:
                out = await run_text(judge, f"FACTS: {json.dumps(x['facts'], ensure_ascii=False, default=str)[:6000]}"
                                            f"\nSTATEMENT: {x['text']}")
                m = re.search(r"[1-5]", out)
                if m:
                    scores.append(int(m.group()))
            except Exception as ex:  # noqa: BLE001
                print("judge error", type(ex).__name__, ex, file=sys.stderr)
        r["groundedness_judge"] = {"mean": round(statistics.mean(scores), 2) if scores else None, "n": len(scores),
                                   "distribution": {k: scores.count(k) for k in range(1, 6)}}
    return {"match": match, "events": len(ev), "model": s.model, "runs": runs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundry", action="store_true")
    ap.add_argument("--langs", nargs="+", default=["en", "ar"])
    ap.add_argument("--match", default="EP-2026-002")
    ap.add_argument("--events", type=int, default=0, help="limit events per Foundry run (0 = full match)")
    ap.add_argument("--out", default=str(ROOT / "docs" / "eval_results.json"))
    a = ap.parse_args()
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "offline_templates": asyncio.run(offline())}
    if a.foundry:
        res["foundry_llm"] = asyncio.run(foundry(a.langs, a.match, a.events))
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    o = res["offline_templates"]
    print(f"offline: {o['clean_pass']}/{o['lines']} clean lines pass; planted caught {o['caught_total']}/"
          f"{o['planted_total']}; by kind {json.dumps(o['planted'])}; latency {o['verifier_latency_us']}")
    for r in res.get("foundry_llm", {}).get("runs", []):
        print(json.dumps({k: v for k, v in r.items() if k != "rejections"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
