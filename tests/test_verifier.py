import asyncio
import json
from pathlib import Path

from agents import MatchOrchestrator, Settings
from agents.verifier import Verifier


DATA = Path(__file__).resolve().parents[1] / "data"


def load_match():
    meta = json.loads((DATA / "EP-2026-002_meta.json").read_text())
    events = [
        json.loads(line)
        for line in (DATA / "EP-2026-002_events.jsonl").read_text().splitlines()
    ]
    return meta, events


def test_correct_line_returns_evidence_for_numbers_and_player():
    meta, _ = load_match()
    verdict = Verifier(meta).check(
        "Sami Garrow scored 2 goals in 75 minutes.",
        {"player": "Sami Garrow", "goals": 2, "minute": 75},
    )

    assert verdict.ok
    claims = {item["claim"] for item in verdict.evidence}
    assert {"Sami Garrow", "2", "75"} <= claims


def test_wrong_number_is_rejected():
    meta, _ = load_match()
    verdict = Verifier(meta).check("Sami Garrow scored 9 goals.", {"player": "Sami Garrow", "goals": 2})

    assert not verdict.ok
    assert any("number 9" in problem for problem in verdict.problems)


def test_wrong_score_pair_is_rejected():
    meta, _ = load_match()
    verdict = Verifier(meta).check("The score is 4-1.", {"score": {"home": 3, "away": 1}})

    assert not verdict.ok
    assert any("pair 4-1" in problem for problem in verdict.problems)


def test_roster_player_absent_from_facts_is_rejected():
    meta, _ = load_match()
    verdict = Verifier(meta).check("Sami Garrow made the pass.", {"event": "a pass"})

    assert not verdict.ok
    assert any("Sami Garrow" in problem for problem in verdict.problems)


def test_invented_capitalised_name_is_rejected():
    meta, _ = load_match()
    verdict = Verifier(meta).check("Marcus Bell scored.", {"event": "a goal"})

    assert not verdict.ok
    assert any("unknown name Marcus Bell" in problem for problem in verdict.problems)


def test_arabic_indic_digits_are_normalised():
    meta, _ = load_match()
    verdict = Verifier(meta).check(
        "Sami Garrow سجل ٢ هدفاً في الدقيقة ٧٥.",
        {"player": "Sami Garrow", "goals": 2, "minute": 75},
    )

    assert verdict.ok
    assert {"2", "75"} <= {item["claim"] for item in verdict.evidence}


def test_offline_match_commentary_is_verified_with_evidence():
    meta, events = load_match()

    async def run_match():
        orchestrator = MatchOrchestrator(meta, settings=Settings())
        items = await orchestrator.start()
        for event in events:
            items.extend(await orchestrator.on_event(event))
        items.extend(await orchestrator.finish())
        return orchestrator, items

    orchestrator, items = asyncio.run(run_match())
    commentary = [payload for kind, payload in items if kind == "commentary"]

    assert commentary
    assert all(item["verified"] is True for item in commentary)
    assert all(
        item["evidence"]
        for item in commentary
        if any(character.isdigit() for character in item["text"])
    )
    assert orchestrator.audit


def test_narrator_rewrites_rejected_number_once(monkeypatch):
    meta, events = load_match()
    shot = next(event for event in events if event["event_id"] == "EP-2026-002-01457")
    goal = next(event for event in events if event["event_id"] == "EP-2026-002-01458")

    class FakeNarrator:
        name = "narrator"

        def __init__(self):
            self.calls = 0

    narrator = FakeNarrator()
    from agents import foundry

    async def fake_run_text(agent, prompt):
        agent.calls += 1
        if agent.calls == 1:
            return "Idris Okafor scores after 99 attempts."
        return "Idris Okafor scores with 0.02 xG."

    monkeypatch.setattr(foundry, "run_text", fake_run_text)

    async def run_goal():
        orchestrator = MatchOrchestrator(
            meta,
            settings=Settings(mode="foundry", retries=0),
            llm_agents={"narrator": narrator},
        )
        items = await orchestrator.start()
        items.extend(await orchestrator.on_event(shot))
        items.extend(await orchestrator.on_event(goal))
        items.extend(await orchestrator.flush())
        return orchestrator, items

    orchestrator, items = asyncio.run(run_goal())
    updates = [payload for kind, payload in items if kind == "commentary_update"]

    assert orchestrator.verify_stats["rewrites"] == 1
    assert narrator.calls == 2
    assert len(updates) == 1
    assert updates[0]["verified"] is True
    assert updates[0]["evidence"]
