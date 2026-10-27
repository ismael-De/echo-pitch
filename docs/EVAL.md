# Echo Pitch: measured evaluation

Every number on this page was produced by [`scripts/eval_verifier.py`](../scripts/eval_verifier.py). The raw output is in [`docs/eval_results.json`](eval_results.json) (run on 27 Oct 2026, 19:31 UTC+3). Nothing here is estimated or hand-edited. Re-run it with:

```bash
python scripts/eval_verifier.py                                    # offline part (no Azure)
LLM_MODE=foundry FOUNDRY_PROJECT_ENDPOINT=... python scripts/eval_verifier.py --foundry --langs en ar es fr pt
```

## Headline

| What | Result |
|---|---|
| Planted factual errors that reached the viewer, real gpt-5-mini lines, numbers and names | **4 of 476** got through (472 caught, 99.2%) |
| Planted errors caught, template lines, numbers and names | **7,005 of 7,005** (100%) |
| Correct lines wrongly rejected (template lines, all 5 languages) | **0 of 3,200** |
| Unverified LLM lines shown to viewers (5 full matches, one per language) | **0 of 170** |
| First-draft pass rate of real gpt-5-mini lines | 173 of 175 (98.9%). Both rejected drafts were fixed by the one rewrite. |
| Groundedness, LLM-as-judge (gpt-5-mini, scale 1 to 5) on the 175 LLM lines that passed the Verifier | **4.77** mean: EN 4.97 · AR 4.97 · ES 4.86 · FR 4.46 · PT 4.57 |
| Verifier latency per line | p50 0.12 ms · p95 0.21 ms (deterministic, no LLM call) |
| gpt-5-mini call latency (writer agents, this run) | p50 3.8 to 4.0 s · p95 5.2 to 6.9 s, depending on language |

**Known limitation (also measured):** a line that names the wrong team was caught **0 of 81 times** (LLM lines) and **0 of 720 times** (template lines). Both teams are legitimate facts in almost every event, so a deterministic check on numbers and names alone cannot tell which side did what. The LLM judge's lower French and Portuguese scores point to the same class of error. The next step is a team-attribution rule (player → club from the roster).

## Method

1. **Lines.** For the offline part we replay all 3 synthetic matches × 5 languages × 2 personas (fan and analyst, with a favourite club and player). Every commentary line, moment card, insight and recap goes through the Verifier, giving 3,200 lines. For the Foundry part we replay match EP-2026-002 once per language with the live Agent Framework agents on Azure AI Foundry (gpt-5-mini). Every LLM draft goes through the Verifier, giving 175 drafts.
2. **Planted errors.** For each line that passed, we corrupt one claim at a time and check the corrupted line again against the same facts:
   - `wrong_number`: one number changed to a value that appears nowhere in the facts.
   - `wrong_score_pair`: the first "a-b" score or stat pair changed.
   - `wrong_player`: a named player replaced by a roster player who is not part of the event.
   - `invented_player`: a named player replaced by a name that is not on the roster.
   - `swapped_team`: the team name replaced by the other team.
3. **Groundedness.** A separate gpt-5-mini judge agent rates each line shown against the exact facts JSON the writer received (5 = fully supported, 1 = contradicts the facts).
4. **Latency.** Verifier time is measured around each check. LLM latency comes from the orchestrator's `agent_trace` records.

## Results by error type (real gpt-5-mini lines, 5 languages)

| Error type | Caught / planted |
|---|---|
| wrong_number | 173 / 174 |
| wrong_score_pair | 91 / 94 |
| wrong_player | 104 / 104 |
| invented_player | 104 / 104 |
| swapped_team | 0 / 81 (limitation) |

Template lines: wrong_number 1,335/1,335 · wrong_score_pair 330/330 · wrong_player 2,670/2,670 · invented_player 2,670/2,670 · swapped_team 0/720.

The few misses on LLM lines happen when the changed value happens to equal another real stat in the same facts, for example a score pair that matches the shots pair. In that case the Verifier sees a number it can source.

## What happens to a rejected line in the product

The writer agent's draft goes to the Verifier. If it is rejected, the draft goes back to the same writer once, with the problems listed. If the rewrite is also rejected, the verified template line that is already on screen stays. The UI shows a 🛡 badge on every line. Clicking it shows the evidence footnotes (claim ← fact). The agent trace shows `verifier.<task> → ok | rejected | fallback`. Every verdict goes into the replay's audit log (`GET /api/replays/{id}/audit`).

Earlier latency and cost measurements of the live pipeline (through the real SSE server) are in [`foundry_eval.json`](foundry_eval.json).
