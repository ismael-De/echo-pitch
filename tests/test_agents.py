import asyncio
import json
import re

import pytest

from agents import MatchOrchestrator, Prefs, Settings
from generator import generate_match

ARABIC = re.compile(r"[\u0600-\u06FF]")


@pytest.fixture(scope="module")
def match():
    return generate_match(seed=58, home="SHF", away="BRT", match_no=2)


def run(meta, events, prefs, settings=None):
    async def go():
        o = MatchOrchestrator(meta, prefs, settings or Settings())
        items = await o.start()
        for e in events:
            items += await o.on_event(e)
        items += await o.finish()
        return o, items
    return asyncio.run(go())


def of(items, kind):
    return [d for k, d in items if k == kind]


def test_from_env_defaults(monkeypatch):
    """Locks the defaults documented in docs/architecture.md."""
    for name in ("LLM_MODE", "LLM_TIMEOUT_S", "LLM_RETRIES", "LLM_MAX_COMPLETION_TOKENS",
                 "LLM_REASONING_EFFORT", "LLM_PERSONA_REWRITE", "FOUNDRY_MODEL",
                 "AZURE_AI_MODEL_DEPLOYMENT_NAME", "FOUNDRY_PROJECT_ENDPOINT",
                 "AZURE_AI_PROJECT_ENDPOINT", "ECHO_FAULT_AGENTS"):
        monkeypatch.delenv(name, raising=False)
    s = Settings.from_env()
    assert s.mode == "offline" and s.timeout_s == 20 and s.retries == 1
    assert s.max_completion_tokens == 400 and s.reasoning_effort == "minimal"
    assert s.persona_rewrite is False and s.model == "gpt-5-mini"
    assert not s.fault_once and not s.fault_always
    assert Settings().timeout_s == 8


def test_settings_env(monkeypatch):
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    monkeypatch.setenv("LLM_MODE", "foundry")
    s = Settings.from_env()
    assert s.mode == "offline" and s.warning
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
    monkeypatch.setenv("ECHO_FAULT_AGENTS", "narrator,moments!")
    s = Settings.from_env()
    assert s.mode == "foundry" and s.model == "gpt-4o-mini"
    assert s.fault_once == {"narrator"} and s.fault_always == {"moments"}


def test_offline_english_full_match(match):
    meta, ev = match
    o, items = run(meta, ev, Prefs("fan", "en"))
    com, cards, recap = of(items, "commentary"), of(items, "moment_card"), of(items, "recap")
    assert len(com) > 40
    goals = [c for c in cards if c["kind"] == "goal"]
    assert len(goals) == sum(meta["final_score"].values())
    assert all(c["why"] and not ARABIC.search(c["why"]) for c in cards)
    assert len(recap) == 1 and meta["home"]["name"] in recap[0]["text"]
    assert of(items, "stats")[-1]["score"] == meta["final_score"]
    json.dumps(items)  # everything must be JSON-serialisable for SSE


def test_offline_arabic(match):
    meta, ev = match
    _, items = run(meta, ev, Prefs("analyst", "ar"))
    texts = [c["text"] for c in of(items, "commentary")] + [c["why"] for c in of(items, "moment_card")]
    assert texts and all(ARABIC.search(t) for t in texts if not t.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")))
    assert ARABIC.search(of(items, "recap")[0]["text"])
    assert all(c["lang"] == "ar" for c in of(items, "moment_card"))


def test_persona_differs_and_overlays(match):
    meta, ev = match
    fav = meta["home"]["lineup"][9]["player_id"]
    _, fan = run(meta, ev, Prefs("fan", "en", "home", fav))
    _, ana = run(meta, ev, Prefs("analyst", "en"))
    fan_goal = [c["text"] for c in of(fan, "commentary") if c["kind"] == "goal"]
    ana_goal = [c["text"] for c in of(ana, "commentary") if c["kind"] == "goal"]
    assert all("xG" in t for t in ana_goal) and not any("xG" in t for t in fan_goal)
    assert any(meta["home"]["name"] + "!" in t or meta["home"]["name"] + "..." in t for t in fan_goal)
    kinds_fan = {o["kind"] for o in of(fan, "overlay")}
    kinds_ana = {o["kind"] for o in of(ana, "overlay")}
    assert "player_tag" in kinds_fan and "goal_banner" in kinds_fan
    assert "shot_xg" in kinds_ana and "shot_xg" not in kinds_fan
    for o in of(fan, "overlay"):
        assert {"overlay_id", "kind", "anchor", "start_s", "duration_s", "payload"} <= set(o)
    starts = [o["start_s"] for o in of(fan, "overlay")]
    assert starts == sorted(starts) or len(set(o["clock"] for o in of(fan, "overlay"))) > 1


def test_retry_recovers(match):
    meta, ev = match
    s = Settings(fault_once={"narrator"})
    o, items = run(meta, ev[:300], Prefs(), s)
    rec = [t for t in o.trace if t["agent"] == "narrator"]
    assert rec[0]["status"] == "recovered" and rec[0]["attempts"] == 2
    assert of(items, "commentary")[0]["source"] == "template"


def test_fallback_when_agent_always_fails(match):
    meta, ev = match
    s = Settings(fault_always={"moments", "narrator"}, retries=1)
    o, items = run(meta, ev, Prefs("fan", "ar"), s)
    assert any(t["status"] == "fallback" for t in o.trace)
    cards = of(items, "moment_card")
    assert cards and all(c["source"] == "safe_template" and c["why"] for c in cards)
    assert all(c["text"] for c in of(items, "commentary"))
    assert of(items, "recap")[0]["source"] == "safe_template"


def test_narrator_commentary_uses_safe_line_after_failure(match):
    meta, ev = match
    o, items = run(meta, ev[:300], Prefs(), Settings(fault_always={"narrator"}, retries=0))
    comments = [c for c in of(items, "commentary") if c["kind"] != "insight"]
    assert comments and all(c["source"] == "safe_template" for c in comments)
    assert all(c["text"] for c in comments)
    assert any(t["agent"] == "narrator" and t["status"] == "fallback" for t in o.trace)


class FakeLLM:
    def __init__(self, fail_first=False):
        self.calls, self.fail_first = 0, fail_first


def test_llm_path_with_fake_agents(match, monkeypatch):
    """Exercise the 'foundry' code path with stub agents (no network)."""
    meta, ev = match
    from agents import foundry

    async def fake_run_text(agent, prompt):
        agent.calls += 1
        if agent.fail_first and agent.calls == 1:
            raise TimeoutError("simulated Foundry timeout")
        return f"[{agent.name}] ok"

    monkeypatch.setattr(foundry, "run_text", fake_run_text)
    stubs = {n: FakeLLM(fail_first=(n == "moments")) for n in ("stats", "moments", "narrator", "persona")}
    for n, a in stubs.items():
        a.name = n
    async def go():
        o = MatchOrchestrator(meta, Prefs("fan", "en"), Settings(mode="foundry", retries=1), llm_agents=stubs)
        items = []
        for e in ev:
            items += await o.on_event(e)
        items += await o.flush()
        return o, items
    o, items = asyncio.run(go())
    assert any(c["source"] == "llm" and c.get("update") for c in of(items, "moment_card"))
    assert any(u["source"] == "llm" for u in of(items, "commentary_update"))
    assert any(t["agent"] == "moments" and t["status"] == "recovered" for t in o.trace)
    assert stubs["stats"].calls > 0 and stubs["narrator"].calls > 0


def test_foundry_agents_build_without_network():
    pytest.importorskip("agent_framework.foundry")
    from agents.foundry import build_agents
    s = Settings(mode="foundry", project_endpoint="https://example.services.ai.azure.com/api/projects/demo",
                 model="gpt-4o-mini")
    agents = build_agents(s, [lambda: {}])
    assert set(agents) == {"stats", "moments", "narrator", "recap", "persona"}


def test_llm_calls_do_not_block_replay(match, monkeypatch):
    """Slow Foundry calls (0.4 s each) run in the background: processing the match stays fast,
    and upgrades arrive later via drain()/flush()."""
    import time
    meta, ev = match
    from agents import foundry

    async def slow_run_text(agent, prompt):
        await asyncio.sleep(0.4)
        return "llm text"

    monkeypatch.setattr(foundry, "run_text", slow_run_text)
    stubs = {n: FakeLLM() for n in ("stats", "moments", "narrator", "persona")}

    async def go():
        o = MatchOrchestrator(meta, Prefs(), Settings(mode="foundry", timeout_s=5), llm_agents=stubs)
        t0 = time.perf_counter()
        items = []
        for e in ev:
            items += await o.on_event(e)
        elapsed = time.perf_counter() - t0
        items += await o.finish()
        return elapsed, items
    elapsed, items = asyncio.run(go())
    n_upgrades = len(of(items, "commentary_update")) + sum(1 for c in of(items, "moment_card") if c.get("update"))
    assert n_upgrades >= 5
    assert elapsed < 0.4 * n_upgrades / 2  # far less than running the LLM calls sequentially
    assert of(items, "recap")[0]["source"] == "llm"


def test_stoppage_windows_and_momentum(match):
    from analytics import momentum, pressure_index
    _, ev = match
    rows = pressure_index(ev)
    keys = [(r["period"], r["minute"]) for r in rows]
    assert (1, 45) in keys and (2, 45) in keys and len(keys) == len(set(keys))
    assert next(r for r in rows if (r["period"], r["minute"]) == (1, 45))["label"] == "45+'"
    m = momentum(ev)
    ts = [r["t"] for r in m]
    assert ts == list(range(len(ts)))
    assert all(-0.9 < r["momentum"] < 0.9 for r in m)
    steps = [abs(a["momentum"] - b["momentum"]) for a, b in zip(m, m[1:])]
    assert max(steps) < 0.6


def test_language_guard():
    from agents.specialists import WrongLanguage, check_language
    check_language("هدف رائع من Pavel Garrow في الدقيقة 86", "ar")
    check_language("Goal for Saltmarsh FC", "en")
    with pytest.raises(WrongLanguage):
        check_language("Goal for Saltmarsh FC, saved by the keeper", "ar")
    with pytest.raises(WrongLanguage):
        check_language("هدف", "en")
