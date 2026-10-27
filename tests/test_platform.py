"""Verifier API, producer approval + audit log, TTS endpoint and the MCP server (stdio + HTTP)."""
import asyncio
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

from app import main, tts
from echo_mcp import server as M


@pytest.fixture(scope="module")
def client():
    from pathlib import Path
    main.DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # test_api points it at a temp dir
    main._load.cache_clear()
    return TestClient(main.app)


def test_verify_endpoint(client):
    ok = client.post("/api/verify", json={"match_id": "EP-2026-002", "text": "Saltmarsh FC win 3-1, xG 2.74-1.89."}).json()
    assert ok["ok"] and any(e["how"] == "pair" for e in ok["evidence"])
    bad = client.post("/api/verify", json={"match_id": "EP-2026-002", "text": "Saltmarsh FC win 4-1."}).json()
    assert not bad["ok"] and "4-1" in bad["problems"][0]
    assert client.post("/api/verify", json={"match_id": "NOPE", "text": "x"}).status_code == 404


def test_mcp_tools_direct():
    assert {m["match_id"] for m in M.list_matches()} >= {"EP-2026-001", "EP-2026-002"}
    st = M.get_match_stats("EP-2026-002")
    assert st["score"] == {"Saltmarsh FC": 3, "Brackenridge Town": 1}
    early = M.get_match_stats("EP-2026-002", minute=30)
    assert early["events_processed"] < st["events_processed"]
    goals = [m for m in M.get_key_moments("EP-2026-002") if m["kind"] == "goal"]
    assert len(goals) == 4
    e = M.get_event("EP-2026-002", goals[0]["event_id"])
    assert e["type"] == "goal"
    v = M.verify_commentary("EP-2026-002", f"{e['player_name']} scores!", event_id=e["event_id"])
    assert v["ok"]
    with pytest.raises(ValueError):
        M.get_match_stats("NOPE")


def test_mcp_over_http(client):
    """Streamable-HTTP MCP endpoint mounted on the web app (what Foundry / remote clients use)."""
    with TestClient(main.app) as c:
        h = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
        r = c.post("/mcp/", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
        assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "echo-pitch"
        r = c.post("/mcp/", headers=h, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert names == {"list_matches", "get_match_stats", "get_key_moments", "get_event", "verify_commentary"}
        r = c.post("/mcp/", headers=h, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "verify_commentary", "arguments": {"match_id": "EP-2026-002", "text": "Saltmarsh FC win 5-0"}}})
        res = json.loads(r.json()["result"]["content"][0]["text"])
        assert res["ok"] is False


def test_mcp_stdio():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def go():
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = StdioServerParameters(command=sys.executable, args=["-m", "echo_mcp"], cwd=root,
                                  env={**os.environ, "PYTHONPATH": root})
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = {t.name for t in (await s.list_tools()).tools}
                out = await s.call_tool("get_match_stats", {"match_id": "EP-2026-002"})
                return tools, json.loads(out.content[0].text)
    tools, st = asyncio.run(go())
    assert "verify_commentary" in tools and st["score"]["Saltmarsh FC"] == 3


def _sse(text):
    cur, out = None, []
    for line in text.splitlines():
        if line.startswith("event: "):
            cur = line[7:]
        elif line.startswith("data: "):
            out.append((cur, json.loads(line[6:])))
    return out


def test_stream_verified_and_audit(client, monkeypatch):
    monkeypatch.setenv("LLM_MODE", "offline")
    r = client.post("/api/replays", json={"match_id": "EP-2026-002", "speed": 60, "start_minute": 85}).json()
    items = _sse(client.get(r["stream_url"] + "?approval=true&lang=ar").text)
    com = [d for k, d in items if k == "commentary"]
    assert com and all(c["verified"] for c in com)
    assert any(k == "verifier" for k, _ in items)
    rec = [d for k, d in items if k == "recap"][0]
    assert rec["verified"] and rec["verifier"]["checked"] > 0
    rid = r["replay_id"]
    assert client.post(f"/api/replays/{rid}/decisions", json={"ref": com[0]["id"], "decision": "approve",
                                                              "text": com[0]["text"]}).status_code == 201
    assert client.post(f"/api/replays/{rid}/decisions", json={"ref": "x", "decision": "maybe"}).status_code == 422
    log = client.get(f"/api/replays/{rid}/audit").json()
    assert log["summary"]["verifier_checks"] > 0 and log["summary"]["producer_approved"] == 1
    assert log["entries"][-1]["task"] == "producer"


def test_tts_not_configured(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    assert client.post("/api/tts", json={"text": "hi", "lang": "en"}).status_code == 503
    assert client.get("/api/config").json()["tts"] == "browser"
    assert client.post("/api/tts", json={"text": "hi", "lang": "xx"}).status_code == 422


def test_tts_azure_called(client, monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "uaenorth")

    async def fake(text, lang, voice=None):
        assert lang == "ar"
        return b"ID3fake"
    monkeypatch.setattr(tts, "synthesize", fake)
    r = client.post("/api/tts", json={"text": "هدف", "lang": "ar"})
    assert r.status_code == 200 and r.content == b"ID3fake" and r.headers["x-voice"] == "ar-SA-HamedNeural"


def test_ssml_escapes_and_voices():
    s = tts.ssml("A <b> & 'c'", "fr")
    assert "fr-FR-HenriNeural" in s and "&lt;b&gt; &amp;" in s
    assert set(tts.VOICES) == {"en", "ar", "es", "fr", "pt", "ru"}


def test_tts_alt_voice_allowlist():
    assert tts.pick("ar", "ar-JO-TaimNeural") == ("ar-JO", "ar-JO-TaimNeural")
    assert tts.pick("ar", None) == ("ar-SA", "ar-SA-HamedNeural")
    assert tts.pick("en", "ar-JO-TaimNeural") == ("en-GB", "en-GB-RyanNeural")  # voice must match the language
    assert tts.pick("ar", "evil<voice>")[1] == "ar-SA-HamedNeural"
    assert "ar-JO-TaimNeural" in tts.ssml("هدف", "ar", "ar-JO-TaimNeural")


def test_index_versioned_assets_and_no_cache(client):
    r = client.get("/")
    assert r.status_code == 200 and "no-cache" in r.headers["cache-control"]
    assert "/static/app.js?v=" in r.text and "/static/style.css?v=" in r.text
    js = client.get("/static/app.js")
    assert js.status_code == 200 and "no-cache" in js.headers["cache-control"]


def test_russian_voice():
    assert tts.pick("ru", None) == ("ru-RU", "ru-RU-DmitryNeural")
    assert tts.pick("ru", "ar-JO-TaimNeural") == ("ru-RU", "ru-RU-DmitryNeural")  # Arabic alt voice never leaks into ru
    s = tts.ssml("Гол! Luca Jessop забивает.", "ru")
    assert "xml:lang='ru-RU'" in s and "ru-RU-DmitryNeural" in s and "Гол!" in s
    assert tts.pick("ar", None) == ("ar-SA", "ar-SA-HamedNeural")
