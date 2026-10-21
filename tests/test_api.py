import json

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    from generator import generate_match
    meta, ev = generate_match(seed=53, match_no=1)
    (d / f"{meta['match_id']}_meta.json").write_text(json.dumps(meta))
    (d / f"{meta['match_id']}_events.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    main.DATA_DIR = d
    main._load.cache_clear()
    return TestClient(main.app)


def test_matches_meta_events(client):
    ms = client.get("/api/matches").json()
    assert ms[0]["match_id"] == "EP-2026-001"
    assert len(client.get("/api/matches/EP-2026-001/meta").json()["home"]["lineup"]) == 11
    assert len(client.get("/api/matches/EP-2026-001/events?upto=10").json()) == 10
    assert client.get("/api/matches/NOPE/meta").status_code == 404


def test_stats(client):
    s = client.get("/api/matches/EP-2026-001/stats?upto=500").json()
    assert s["events_processed"] == 500 and "key_moments" in s


def test_replay_validation(client):
    assert client.post("/api/replays", json={"match_id": "EP-2026-001", "speed": 5}).status_code == 422
    assert client.post("/api/replays", json={"match_id": "EP-2026-001", "speed": 61}).status_code == 422


def test_replay_stream_and_state(client):
    r = client.post("/api/replays", json={"match_id": "EP-2026-001", "speed": 60, "start_minute": 0}).json()
    events, kinds = [], []
    with client.stream("GET", r["stream_url"] + "?stats_every=5") as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        cur = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                cur = line[7:]
                kinds.append(cur)
            elif line.startswith("data: ") and cur == "match_event":
                events.append(json.loads(line[6:]))
            if len(events) >= 6:
                break
    assert kinds[0] == "meta" and "stats" in kinds
    assert [e["event_id"] for e in events] == [f"EP-2026-001-{i:05d}" for i in range(1, 7)]
    st = client.get(r["state_url"]).json()
    assert st["replay_id"] == r["replay_id"] and st["speed"] == 60 and not st["finished"]
    assert client.delete(f"/api/replays/{r['replay_id']}").status_code == 200


def test_replay_start_minute(client):
    r = client.post("/api/replays", json={"match_id": "EP-2026-001", "speed": 60, "start_minute": 80}).json()
    with client.stream("GET", r["stream_url"]) as resp:
        cur = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                cur = line[7:]
            elif line.startswith("data: ") and cur == "match_event":
                assert json.loads(line[6:])["minute"] >= 80
                break


def _collect(client, url, stop_kind, limit=4000):
    kinds, data, cur = [], [], None
    with client.stream("GET", url) as resp:
        for line in resp.iter_lines():
            if line.startswith("event: "):
                cur = line[7:]
                kinds.append(cur)
            elif line.startswith("data: "):
                data.append((cur, json.loads(line[6:])))
                if cur == stop_kind or len(data) > limit:
                    break
    return kinds, data


def test_agent_stream_arabic(client):
    r = client.post("/api/replays", json={"match_id": "EP-2026-001", "speed": 60, "start_minute": 0}).json()
    kinds, data = _collect(client, r["stream_url"] + "?lang=ar&persona=analyst", "commentary")
    com = [d for k, d in data if k == "commentary"][0]
    assert com["lang"] == "ar" and any("\u0600" <= ch <= "\u06ff" for ch in com["text"])
    assert kinds[0] == "meta" and "stats" in kinds


def test_web_ui_served(client):
    html = client.get("/").text
    assert "Echo Pitch" in html and "/static/app.js" in html
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/config").json()["llm_mode"] in ("offline", "foundry")
