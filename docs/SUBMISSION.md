# Submission checklist

Microsoft × Premier League **"Inside the Game"** Developer Hackathon. Solo entry by Ismael Sarhan.
**Deadline: Wednesday 28 Oct 2026, 09:59 Asia/Amman (UTC+3).** Submit on Tuesday if you can.
Primary category: **Multi-Agent**. Secondary: **Foundry**.

Marks: ✅ checked in this repo on 23 Oct 2026 · ⬜ still yours to do.

## Checked in the repo

| Check | Status | Evidence |
|---|---|---|
| Live Azure URL is in the README | ✅ | https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io (README, first screen). The app scales to zero, so the first load can take about 20 seconds. Warm it before you record. |
| Fresh clone runs offline | ✅ | README **Run it** matches the PowerShell steps in `AGENTS.md`: Python 3.11+, venv, `pip install -r requirements.txt`, `$env:LLM_MODE="offline"`, `uvicorn app.main:app --port 8000`. The three demo matches are already in `data/`, so `python -m generator` is optional. Leave `.env` uncopied for this path. |
| No secrets in the tree or the history | ✅ | Every commit through `c0aa210` (14 commits) was searched for API keys, account keys, private keys, `sk-` tokens, AWS-style access keys and GitHub tokens. No matches. A real `.env` was never committed. Foundry URLs in git are the placeholder `https://<account>.services.ai.azure.com/api/projects/<project>` or the test fixtures `https://x.services.ai.azure.com/api/projects/p` and `https://example.services.ai.azure.com/api/projects/demo`. The username `00000000-0000-0000-0000-000000000000` in `infra/deploy_aca.sh` is the public `az acr login --expose-token` username. The registry token is piped on stdin and is not stored. |
| `.env.example` lists the runtime knobs | ✅ | Mode, endpoint (and the `AZURE_AI_PROJECT_ENDPOINT` alias in a comment), model, `FOUNDRY_CREDENTIAL=auto`, timeout, retries, token cap, reasoning effort, persona rewrite, `ECHO_FAULT_AGENTS`. Budget limits and `ECHO_DATA_DIR` are commented so copying the file keeps the code defaults (6 per IP per hour, 150 per UTC day, 4 concurrent, 200 replays). No keys. |
| Video script matches the UI | ✅ | `docs/video_script.md` on-screen column follows `web/index.html` and `web/app.js`. Details below. |
| Tests | ✅ | Offline suite is 86 passed, 2 skipped (v2). The two Foundry tests stay skipped unless `ECHO_FOUNDRY_IT=1`. |
| Five languages, synthetic data | ✅ | EN / AR (RTL, scoreboard stays LTR) / ES / FR / PT. Clubs and players are fictional. |
| GitHub Copilot | ✅ | Copilot CLI added `test_narrator_commentary_uses_safe_line_after_failure` in `tests/test_agents.py`. README, pitch and plan describe only that. |

## v2 update (27 Oct 2026, evening)

| Check | Status | Evidence |
|---|---|---|
| Verifier (Guard) agent | ✅ | `agents/verifier.py`, wired into `agents/orchestrator.py`. 🛡 badge + evidence footnotes in the UI, `verifier` pill in the agent strip |
| Measured eval | ✅ | `scripts/eval_verifier.py` → `docs/eval_results.json` → `docs/EVAL.md`. README top table copies those numbers |
| Spoken commentary | ✅ | Azure AI Speech F0 resource `echo-pitch-speech` (UAE North). The key is a Container Apps secret. `POST /api/tts` |
| Audio-first mode | ✅ | ♿ button / key `A` / `?a11y=1` |
| MCP server | ✅ | `echo_mcp/`, live at `/mcp/`. Copilot CLI and Foundry agent runs are saved in `docs/` |
| Producer approval + audit log | ✅ | 🎬 button / `?approval=1`, `GET /api/replays/{id}/audit` |
| Tests | ✅ | 86 passed, 2 skipped (offline), run 3 times in a row after each feature |
| Live end-to-end | ✅ | `python scripts/e2e_live.py` (5 languages, verifier, audio, approval, audit, MCP) |
| GitHub Copilot | ✅ | Copilot CLI wrote `tests/test_verifier.py` and was used as an MCP client |
| New demo video | ✅ | `echo_pitch_demo_v2.mp4` (not uploaded yet) |

## What the UI actually shows (for the video)

- **Kick off** and **Restart** call `start(0)`. A late start happens only when the page is opened with `?start=` and `autoplay=1`. After that, leave those buttons alone.
- The match menu shows **Saltmarsh FC v Brackenridge Town**, not the id `EP-2026-002`. Speed defaults to **30**. The recording URLs set **60**.
- The mode badge starts as the word `offline` and updates when the stream sends `meta`. A Foundry run then reads **Azure AI Foundry**. An offline run stays **offline agents**, and commentary chips stay on `TEMPLATE`.
- Footer: label **Agents** (Arabic **الوكلاء**), pills **Stats → Moments → Narrator → Persona → 🛡 Verifier** (names stay English). Green is `ok`, amber is `recovered`, red is `fallback`.
- Trace text looks like `86' narrator.goal → ok · llm · 1234.0ms`. The attempts phrase appears when attempts is greater than 1: `recovered (2 attempts)`.
- A healthy Foundry run shows green `ok` and a chip that fades from `TEMPLATE` to `LLM`. Amber retry needs the server started with `ECHO_FAULT_AGENTS=narrator` (first call only; a later upgrade can still become `LLM`). Red fallback needs `ECHO_FAULT_AGENTS=narrator!` (every call, chip stays `SAFE_TEMPLATE`). Restart the server between those two. They are local clips. The live app does not set that variable.
- Language menu: **English, العربية, Español, Français, Português**. Choosing العربية sets `dir=rtl`, clears the ticker and continues the same replay. The scoreboard and the **ECHO PITCH** brand stay left to right. While a replay is running the button reads **↻ إعادة**. Analyst reads **محلّل**, Club **النادي**, Player **اللاعب**.
- Stored minute 85 is on-screen clock **86'**. The Pavel Garrow goal banner is `GOAL! Pavel Garrow · 2-1`.
- Full time opens a modal titled **Full-time recap** (Arabic **ملخص المباراة**): score line, paragraph, moment chips, Close. The repo URL is an editor card after that modal.

At 60× on EP-2026-002, wall time from replay start to the Pavel goal (on-screen 86') and to the final whistle:

| `start` | Pavel Garrow | Full time |
|---|---|---|
| 0 | 88 s | 95 s |
| 66 | 20 s (Idris Okafor goal also fires at 6 s) | 26 s |
| 72 | 13 s | 20 s |
| 82 | 4 s (README jump-in link) | 10 s |
| 88 | Luca Jessop at 2 s, clock 90+1' | 4 s |

The goal shot in the script uses `start=72`. The README jump-in link stays `start=82`. They are different on purpose.

## Still to do before the deadline

- ⬜ Rewrite `docs/video_script.md` in your own words. Judges notice a generic script. Keep the shots.
- ⬜ Record under 2:00 (target 1:50). Say **Multi-Agent** once. GitHub Copilot may be mentioned only for the narrator fallback test it wrote.
- ⬜ Upload the video to YouTube as **Public**, with time to spare before Wednesday morning.
- ⬜ Make the repo public (do this yourself, on the 27th):

```bash
gh repo edit ismael-De/echo-pitch --visibility public --accept-visibility-change-consequences
```

- ⬜ Fill in the hackathon submission form. Point it at the public repo, the public video and the live URL.
- ✅ GitHub Copilot: one real edit (narrator fallback test), README row updated.
- ⬜ Innovation Studio, if that account step is still open (`docs/PLAN.md`, Thu 22).

## Leave alone

- Budget limits in `app/budget.py`: 6 Foundry streams per IP per hour, 150 per day, 4 concurrent. Over the limit the app uses offline templates.
- Do not put keys in git. Foundry on Azure uses the managed identity.
- Do not deploy or run `az` unless you mean to spend the student credit.
