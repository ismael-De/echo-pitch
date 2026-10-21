"""Full-match evaluation through the running server (real SSE, real agents).

python scripts/foundry_eval.py --base http://127.0.0.1:8000 --match EP-2026-002 --speed 60 --lang en ar
Writes docs/foundry_eval.json with lag, upgrade latency, LLM/fallback counts, token usage and samples.
"""
import argparse
import asyncio
import json
import time

import httpx

PRICE_IN, PRICE_OUT = 0.25 / 1e6, 2.00 / 1e6  # USD per token, gpt-5-mini list price (check Azure pricing page)


async def run(base, match, speed, lang, persona, club):
    async with httpx.AsyncClient(base_url=base, timeout=None) as c:
        r = (await c.post("/api/replays", json={"match_id": match, "speed": speed})).json()
        h1_end = None
        t0 = time.perf_counter()
        rep = {"lang": lang, "persona": persona, "lags": [], "upgrades": [], "traces": [], "commentary": {},
               "cards": {}, "recap": None, "usage": None}
        params = {"lang": lang, "persona": persona}
        if club:
            params["club"] = club
        cur = None
        async with c.stream("GET", r["stream_url"], params=params) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    cur = line[7:]
                    continue
                if not line.startswith("data: "):
                    continue
                d, now = json.loads(line[6:]), time.perf_counter() - t0
                if cur == "match_event":
                    gs = d["minute"] * 60 + d["second"]
                    if d["period"] == 1:
                        h1_end = gs
                    else:
                        gs = (h1_end or 2700) + 1 + gs - 2700
                    rep["lags"].append(now - gs / speed)
                elif cur == "commentary":
                    rep["commentary"][d["id"]] = {**d, "t": now}
                elif cur == "commentary_update":
                    o = rep["commentary"].get(d["id"], {})
                    rep["upgrades"].append({"kind": "commentary", "delay_s": round(now - o.get("t", now), 2),
                                            "template": o.get("text"), "llm": d["text"], "clock": o.get("clock")})
                elif cur == "moment_card":
                    if d.get("update"):
                        o = rep["cards"].get(d["moment_id"], {})
                        rep["upgrades"].append({"kind": "moment", "delay_s": round(now - o.get("t", now), 2),
                                                "title": d["title"], "clock": d["clock"], "template": o.get("why"),
                                                "llm": d["why"]})
                    rep["cards"][d["moment_id"]] = {**d, "t": now}
                elif cur == "agent_trace":
                    rep["traces"].append(d)
                elif cur == "recap":
                    rep["recap"] = d
                elif cur == "usage":
                    rep["usage"] = d
                elif cur == "end":
                    break
        rep["wall_s"] = round(time.perf_counter() - t0, 1)
        return rep


def summarise(rep):
    lags = sorted(rep["lags"])
    lat = [t["latency_ms"] for t in rep["traces"] if t.get("source") == "llm"]
    st = {}
    for t in rep["traces"]:
        st[t["status"]] = st.get(t["status"], 0) + 1
    u = rep["usage"] or {}
    tin = sum(v["input_tokens"] for v in u.values())
    tout = sum(v["output_tokens"] for v in u.values())
    calls = sum(v["calls"] for v in u.values())
    pct = lambda a, q: a[min(len(a) - 1, int(q * len(a)))] if a else None
    return {"lang": rep["lang"], "persona": rep["persona"], "wall_s": rep["wall_s"],
            "event_lag_s": {"p50": round(pct(lags, .5), 2), "p95": round(pct(lags, .95), 2), "max": round(lags[-1], 2)},
            "llm_latency_ms": {"p50": pct(sorted(lat), .5), "p95": pct(sorted(lat), .95), "n": len(lat)},
            "upgrade_delay_s": {"p50": pct(sorted(x["delay_s"] for x in rep["upgrades"]), .5),
                                "max": max((x["delay_s"] for x in rep["upgrades"]), default=None)},
            "trace_status": st, "llm_calls": calls, "tokens_in": tin, "tokens_out": tout,
            "cost_usd": round(tin * PRICE_IN + tout * PRICE_OUT, 4), "recap_source": (rep["recap"] or {}).get("source"),
            "usage": u}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--match", default="EP-2026-002")
    ap.add_argument("--speed", type=float, default=60)
    ap.add_argument("--lang", nargs="+", default=["en", "ar"])
    ap.add_argument("--out", default="docs/foundry_eval.json")
    a = ap.parse_args()
    jobs = [run(a.base, a.match, a.speed, lg, "fan" if lg == "en" else "analyst", "home" if lg == "en" else None)
            for lg in a.lang]
    reps = await asyncio.gather(*jobs)
    out = {"match": a.match, "speed": a.speed, "runs": []}
    for rep in reps:
        out["runs"].append({"summary": summarise(rep), "upgrades": rep["upgrades"], "recap": rep["recap"],
                            "failures": [t for t in rep["traces"] if t["status"] != "ok"]})
    with open(a.out, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    for r in out["runs"]:
        print(json.dumps(r["summary"], ensure_ascii=False))


asyncio.run(main())
