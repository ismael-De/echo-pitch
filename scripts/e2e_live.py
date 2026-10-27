"""End-to-end checks against a running Echo Pitch (default: the live Azure URL).

python scripts/e2e_live.py [--base URL]
Checks per language (en ar es fr pt): SSE replay with producer approval on, every commentary line verified with
evidence, Verifier stats, recap, Azure Speech audio, audit log + producer decision; plus /api/verify and MCP.
"""
import argparse
import asyncio
import json
import sys
import time

import httpx

LANGS = ["en", "ar", "es", "fr", "pt", "ru"]


def sse(text):
    cur, out = None, []
    for line in text.splitlines():
        if line.startswith("event: "):
            cur = line[7:]
        elif line.startswith("data: "):
            out.append((cur, json.loads(line[6:])))
    return out


async def mcp_check(base):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    async with streamable_http_client(base + "/mcp/") as streams:
        r, w = streams[0], streams[1]
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            good = json.loads((await s.call_tool("verify_commentary", {"match_id": "EP-2026-002",
                               "text": "Saltmarsh FC beat Brackenridge Town 3-1."})).content[0].text)
            bad = json.loads((await s.call_tool("verify_commentary", {"match_id": "EP-2026-002",
                              "text": "Saltmarsh FC beat Brackenridge Town 4-1."})).content[0].text)
            st = json.loads((await s.call_tool("get_match_stats", {"match_id": "EP-2026-002"})).content[0].text)
    return {"tools": tools, "true_line_ok": good["ok"], "false_line_rejected": not bad["ok"],
            "final_score": st["score"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base, timeout=120)
    res, fails = {"base": a.base, "at": time.strftime("%Y-%m-%d %H:%M:%S%z")}, []
    check = lambda cond, msg: cond or fails.append(msg)
    r = c.get("/")
    check(r.status_code == 200 and "ag-verifier" in r.text and "a11yBtn" in r.text, "index missing new UI")
    cfg = c.get("/api/config").json()
    res["config"] = cfg
    check(cfg["tts"] == "azure_speech", "Azure Speech not configured")
    res["langs"] = {}
    for lg in LANGS:
        rep = c.post("/api/replays", json={"match_id": "EP-2026-002", "speed": 60, "start_minute": 84}).json()
        items = sse(c.get(rep["stream_url"], params={"lang": lg, "approval": "true"}).text)
        kinds = [k for k, _ in items]
        com = [d for k, d in items if k == "commentary"]
        upd = [d for k, d in items if k == "commentary_update"]
        recap = next((d for k, d in items if k == "recap"), None)
        vtr = [d for k, d in items if k == "agent_trace" and d.get("agent") == "verifier"]
        mode = next((d.get("llm_mode") for k, d in items if k == "meta"), None)
        audio = c.post("/api/tts", json={"text": (com[0]["text"] if com else "test")[:300], "lang": lg})
        dec = c.post(f"/api/replays/{rep['replay_id']}/decisions",
                     json={"ref": com[0]["id"] if com else "x", "decision": "approve", "text": "ok"})
        audit = c.get(f"/api/replays/{rep['replay_id']}/audit").json()["summary"]
        row = {"llm_mode": mode, "commentary": len(com), "all_verified": all(x["verified"] for x in com),
               "with_evidence": sum(bool(x["evidence"]) for x in com), "llm_updates": len(upd),
               "updates_pending_for_producer": sum(bool(x.get("pending")) for x in upd),
               "updates_verified": all(x.get("verified") for x in upd), "verifier_traces": len(vtr),
               "recap_verified": bool(recap and recap.get("verified")), "recap_source": recap and recap["source"],
               "verifier_stats": next((d for k, d in items if k == "verifier"), None),
               "tts": [audio.status_code, audio.headers.get("content-type"), len(audio.content), audio.headers.get("x-voice")],
               "decision_status": dec.status_code, "audit": audit, "ended": "end" in kinds}
        res["langs"][lg] = row
        check(row["ended"] and com and row["all_verified"] and row["recap_verified"], f"{lg}: stream/verifier")
        check(row["with_evidence"] > 0, f"{lg}: no evidence")
        check(audio.status_code == 200 and audio.headers.get("content-type") == "audio/mpeg" and len(audio.content) > 2000,
              f"{lg}: tts")
        check(dec.status_code == 201 and audit["producer_approved"] == 1 and audit["verifier_checks"] > 0, f"{lg}: audit")
        check(not upd or row["updates_pending_for_producer"] == len(upd), f"{lg}: approval mode not pending")
    v = c.post("/api/verify", json={"match_id": "EP-2026-002", "text": "Omar Marlow scores for Saltmarsh FC, 5-0."}).json()
    res["api_verify_rejects_false_line"] = not v["ok"]
    check(not v["ok"], "/api/verify accepted a false line")
    res["mcp"] = asyncio.run(mcp_check(a.base))
    check(len(res["mcp"]["tools"]) == 5 and res["mcp"]["true_line_ok"] and res["mcp"]["false_line_rejected"], "mcp")
    res["failures"] = fails
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
