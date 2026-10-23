# GROK.md: context for Grok CLI (same as AGENTS.md)

## Project
**Echo Pitch** is a multi-agent football match storyteller built for the **Microsoft × Premier League "Inside the Game" Developer Hackathon**.
It replays synthetic match events over SSE and produces live commentary, "why it matters" moment cards, timed broadcast overlays and a full-time recap, personalised for an Analyst or a Fan, a favourite club and a favourite player, in **EN / AR (RTL) / ES / FR / PT**.
All data is fictional and synthetic.

- **Deadline:** 28 Oct 2026, 9:59 AM Amman (UTC+3). Solo entry by Ismael Sarhan.
- **Category:** Multi-Agent (primary), Foundry (secondary).
- **Judging (20% each):** technological implementation · agentic design & innovation · real-world impact · UX & presentation · category fit. The README's judging map must stay accurate, and **the docs must match the code exactly** (past winners were disqualified for mismatches).
- **Plan and status:** `docs/PLAN.md`. Architecture: `docs/architecture.md`. Pitch: `docs/pitch.md`. Video script draft: `docs/video_script.md`.

## Architecture (short)
Generator → replay service (FastAPI, SSE, 10–60×) → orchestrator with a shared blackboard → 4 Microsoft Agent Framework agents (Stats with function tools, Moments, Narrator, Persona) on a Foundry `gpt-5-mini` deployment → web UI.
Templates render every line instantly. LLM upgrades stream in the background (`commentary_update`). Every agent call has a timeout, retries and a template fallback, all reported as `agent_trace`.
See `docs/architecture.md`.

## Folder map
```
app/main.py        FastAPI app (entrypoint app.main:app), SSE replay endpoints, serves web/
app/budget.py      spend guard (Foundry stream rate limits)
agents/            config.py (env), orchestrator.py, specialists.py, foundry.py (Agent Framework),
                   templates.py + templates_intl.py (offline text, all 5 languages)
analytics/stats.py deterministic stats: possession, xG, pass difficulty, pressing, momentum
generator/         seeded synthetic match generator (python -m generator)
data/              3 demo matches (EP-2026-001..003, meta + events JSONL)
web/               index.html + app.js (broadcast UI, overlays, language dropdown, RTL)
tests/             pytest suite (offline; Foundry test skipped unless ECHO_FOUNDRY_IT=1)
scripts/           foundry_eval.py, screenshot.py (Playwright)
infra/deploy_aca.sh  Azure Container Apps deploy
Dockerfile, .github/workflows/ci.yml
```

## Run locally on Windows (offline, no Azure cost)
Needs Python 3.11+ and git. In PowerShell:
```powershell
git clone https://github.com/ismael-De/echo-pitch.git
cd echo-pitch
python -m venv .venv
.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
$env:LLM_MODE="offline"
uvicorn app.main:app --port 8000
# open http://localhost:8000
```
Tests (in the same activated venv):
```powershell
$env:LLM_MODE="offline"; python -m pytest -q     # expect 66 passed, 2 skipped
```
Offline mode uses templates only and makes no Azure calls. Do **not** create a `.env` with `LLM_MODE=foundry` unless Ismael asks. Foundry mode needs `az login` and costs credit.
Optional: `python -m generator --demo --out data/` regenerates the demo matches (they are already committed).

## Deployment (do not touch without asking)
- Live: https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io
- Azure resource group `echo-pitch-rg`: container app `echo-pitch-web`, environment `echo-pitch-std`, user-assigned identity `echo-pitch-id` (AcrPull + Cognitive Services User, so no keys), registry `echopitch11913`.
- Redeploy = `infra/deploy_aca.sh`. **Never run deploys, `az` commands, or change Azure resources without Ismael's explicit OK.** The credit is limited (Azure for Students).

## Team workflow
- **Grok** (Grok CLI on Ismael's Windows PC) writes code.
- **Grok Bot** (on its own computer) reviews, tests, merges into main and redeploys to Azure.

Rules for Grok:
1. Always `git checkout main && git pull` first.
2. Work on a new branch named `grok/<short-topic>` (e.g. `git checkout -b grok/mobile-layout`). **Never commit to main.**
3. Keep each branch to one focused change.
4. Run `$env:LLM_MODE="offline"; python -m pytest -q` before pushing. All tests must pass.
5. Push the branch (`git push -u origin grok/<short-topic>`) and open a PR with `gh pr create --base main`, or just push and tell Ismael the branch name.
6. The PR description says **what changed, why, and how to test**.

Grok Bot then reviews the PR, runs the tests, merges into main, and redeploys to Azure with `infra/deploy_aca.sh`.

### How to hand off
When Grok is done, Ismael tells Grok Bot the branch or PR name (e.g. "review grok/mobile-layout" or "PR #3").

## Rules
1. Keep **all tests passing** (`LLM_MODE=offline python -m pytest -q`). Add tests for new behaviour.
2. **Never commit secrets**: no `.env`, keys, endpoints with keys, or tokens. `.env` is gitignored; only `.env.example` is tracked.
3. Keep **all 5 languages (EN/AR/ES/FR/PT)** working: any new user-facing string needs all 5 in `agents/templates*.py` / `web/app.js`, and Arabic must stay RTL-correct (scoreboard stays LTR).
4. Don't weaken the **rate limits** in `app/budget.py` (6 Foundry streams per IP per hour, 150 per day, 4 concurrent). Over the limit → offline fallback, never an error.
5. The broadcast must never block on an LLM call. Keep the template-first, background-upgrade design and the retry/fallback traces.
6. Small, focused commits on a `grok/<topic>` branch (see Team workflow) with clear messages. Update README/docs in the same commit when behaviour changes, so the docs always match the code.
7. Data stays synthetic and fictional (no real clubs or players).
8. Don't make the repo public (planned for Ismael on 27 Oct).

## Prioritised improvement ideas (from docs/PLAN.md)
1. **Real GitHub Copilot usage** (Ismael's own edit), then update the "GitHub Copilot (planned)" row in the README truthfully.
2. **Docs-vs-code audit:** every claim in README/architecture (test counts, agents, env vars, languages) must match the code. Example: the README test section says "45 tests", but the suite now has 66 passing plus 2 skipped.
3. **Demo/video polish:** make the agent strip, retry (`ECHO_FAULT_AGENTS=narrator`) and fallback (`narrator!`) easy to show, plus an Arabic "wow" moment.
4. **Real-world impact:** surface cost per match per viewer and audience reach in the UI or README.
5. **UX:** first-load experience (the app scales to zero, so cold starts take ~20 s), mobile layout, accessibility, clearer overlays.
6. Submission checklist for the 27th: video Public on YouTube, repo public, form filled.
