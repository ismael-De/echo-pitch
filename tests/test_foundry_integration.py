"""Live Microsoft Foundry integration test.

Skipped unless real credentials are configured:
    ECHO_FOUNDRY_IT=1 FOUNDRY_PROJECT_ENDPOINT=... FOUNDRY_MODEL=gpt-5-mini python -m pytest tests/test_foundry_integration.py
(uses `az login` / DefaultAzureCredential). Costs well under one US cent per run.
"""
import asyncio
import os
import re

import pytest

if os.environ.get("ECHO_FOUNDRY_IT"):
    from agents.config import load_dotenv
    load_dotenv()  # pick up the gitignored .env

pytestmark = pytest.mark.skipif(
    not (os.environ.get("ECHO_FOUNDRY_IT") and os.environ.get("FOUNDRY_PROJECT_ENDPOINT") and os.environ.get("FOUNDRY_MODEL")),
    reason="set ECHO_FOUNDRY_IT=1, FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL to run live Foundry tests")


@pytest.fixture(scope="module")
def setup():
    from agents import Settings
    from generator import generate_match
    s = Settings.from_env()
    s.mode = "foundry"
    return s, generate_match(seed=58, home="SHF", away="BRT", match_no=2)


def _run(settings, meta, events, prefs, n):
    from agents import MatchOrchestrator

    async def go():
        o = MatchOrchestrator(meta, prefs, settings)
        items = []
        for e in events[:n]:
            items += await o.on_event(e)
        items += await o.flush(timeout=60)
        return o, items
    return asyncio.run(go())


def test_live_moment_upgrade_en(setup):
    from agents import Prefs
    s, (meta, ev) = setup
    n = next(i for i, e in enumerate(ev) if e["type"] == "save") + 2  # first key save (~2')
    o, items = _run(s, meta, ev, Prefs("fan", "en", "home"), n)
    ups = [d for k, d in items if k == "moment_card" and d.get("update")]
    assert ups, [d for k, d in items if k == "agent_trace"]
    assert ups[0]["source"] == "llm" and len(ups[0]["why"]) > 20
    u = o.usage()["moments"]
    assert u["calls"] >= 1 and u["output_tokens"] <= s.max_completion_tokens + 50


def test_live_arabic_commentary(setup):
    from agents import Prefs
    s, (meta, ev) = setup
    n = next(i for i, e in enumerate(ev) if e["type"] == "save") + 2
    _, items = _run(s, meta, ev, Prefs("analyst", "ar"), n)
    texts = [d["text"] for k, d in items if k == "commentary_update"] + \
            [d["why"] for k, d in items if k == "moment_card" and d.get("update")]
    assert texts and all(re.search(r"[\u0600-\u06FF]", t) for t in texts)
