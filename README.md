# Echo Pitch: the multi-agent match storyteller

> **Every match, explained, for every fan.** Echo Pitch turns a live stream of synthetic football events into
> explainable match intelligence: live commentary, "why it matters" moment cards, timed broadcast overlays and
> a full-time recap. It is personalised for an analyst or a casual fan, in English, Arabic, Spanish, French or Portuguese, around your club
> and your player.

Built for the **Microsoft × Premier League "Inside the Game" Developer Hackathon**. It uses Microsoft Foundry
and Microsoft Agent Framework, and runs live on Azure Container Apps.
All clubs, players and data are **fictional and synthetic**.

**▶ Live demo: [echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io](https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io)** (Azure Container Apps, scales to zero, so the first load can take ~20 s).

![Echo Pitch replay](docs/replay.gif)

## Hackathon category

**Primary: Multi-Agent.** Four specialist agents (Stats with function tools, Moments, Narrator, Persona) are
coordinated by an orchestrator that shares match state, retries failed calls and falls back to deterministic
templates, so the broadcast never stalls. **Also relevant: Foundry.** Every agent runs on a `gpt-5-mini`
deployment in a Microsoft Foundry project, measured at about $0.01 per match per viewer (see below).

| Judging criterion | Where to look |
|---|---|
| Technological implementation | synthetic generator (`generator/`), tests + CI, Foundry eval (`docs/foundry_eval.json`) |
| Agentic design & innovation | [Architecture](#architecture), retry/fallback trace bar in the UI |
| Real-world impact | per-viewer personalisation (Fan/Analyst, club, player) in English, Arabic, Spanish, French and Portuguese |
| UX & presentation | the replay UI below, demo video |

![Echo Pitch UI](docs/ui.png)

## The problem

Broadcast graphics and data feeds tell viewers *what* happened (a shot, 0.41 xG, 52% possession), but rarely
*why it matters*. And every viewer gets the same output. A data-hungry analyst and a first-time fan in Amman or
Lagos want very different stories from the same match (about 1,900 events). Writing those stories by hand, live, in several
languages, does not scale.

## What Echo Pitch does: the five pipeline stages (Rules §4.1)

| Stage | What the rules ask for | How Echo Pitch does it | Code |
|---|---|---|---|
| **1. Ingest** | synthetic events as they happen | A seedable generator produces about 1,900 football-realistic events per match (passes, carries, shots, tackles, pressure, possession changes, fouls, goals, saves). A replay service streams them over SSE at 10–60×. | `generator/`, `app/main.py` |
| **2. Interpret** | stats, patterns, context | Deterministic analytics: possession, pass difficulty (0–100), xG timeline, pressing index, rolling momentum, key-moment candidates | `analytics/stats.py` |
| **3. Explain** | *why* a moment matters | The **Moments agent** explains each moment through game state (lead, equaliser, cushion), timing, with or against the run of play, xG probability, *control vs chaos* and pressure shifts | `agents/` |
| **4. Render** | on-screen, alongside the match | Timed, machine-readable **overlay cards** (`start_s`, `duration_s`, `anchor`, `payload`): goal banner, shot xG, pass difficulty, speed alert, player tag, stat bar, moment lower-third. A broadcast-style web UI renders them. | `agents/orchestrator.py`, `web/` |
| **5. Personalise** | analyst vs fan, club, player, language | The **Persona agent** has Analyst and Fan modes, a favourite-club perspective, a favourite-player focus (★ tags on every touch) and EN/AR/ES/FR/PT output (full RTL for Arabic) | `agents/specialists.py`, `web/app.js` |

It also covers the suggested features: player identification (name tags plus speed alerts above thresholds),
pass quality (distance, accuracy, difficulty), ball and shot speed, narratives and recaps, explainability, data
innovation, and multi-language storytelling.

## Architecture

```mermaid
flowchart LR
  subgraph Data["Synthetic data"]
    G["Generator<br/>(seeded possession-chain sim)"] --> D[("match meta + events JSONL")]
  end
  D --> R["Replay service<br/>10–60× clock"]
  R -->|events| O
  subgraph O["Orchestrator (shared match state)"]
    direction LR
    S["Stats agent<br/>insights + tools"]
    M["Moments agent<br/>why it matters"] --> P["Persona agent<br/>analyst/fan · club · player"]
    N["Narrator agent<br/>commentary + recap"] --> P
    S ~~~ M
  end
  O <-->|"async LLM calls"| F["Microsoft Foundry<br/>model deployment"]
  O -->|"SSE: commentary · moment_card · overlay · stats · agent_trace · recap"| UI["Web UI<br/>pitch · overlays · ticker · momentum"]
  subgraph Azure["Azure Container Apps"]
    R
    O
    UI
  end
```

More detail is in [docs/architecture.md](docs/architecture.md).

### Agents (Microsoft Agent Framework)

| Agent | Role | Inputs and tools |
|---|---|---|
| **Stats** | Owns every number and never invents one. Gives periodic insights. | Agent Framework function tools: `get_live_stats`, `get_key_moments`, `get_explainability` (wrapping `analytics/`) |
| **Moments** | Explains why a moment matters | Moment JSON plus context: margin, momentum before the action, xG, pressing phase |
| **Narrator** | Live commentary lines and the full-time recap, in EN, AR, ES, FR and PT. The recap is a separate Foundry agent (`echo-recap`) | Event facts, style, language |
| **Persona** | Shapes output for the viewer and decides which overlays to show | Persona, favourite club and player, language |

Each agent is an `agent_framework.Agent` on a shared `agent_framework.foundry.FoundryChatClient`, authenticated
with `DefaultAzureCredential` (a managed identity on Azure, so there are no keys).

### Shared state, handoffs and failure recovery

- **Shared state (blackboard):** the orchestrator holds the event log, score, fouls, moment log and agent trace.
  Every agent reads from it, and the Stats tools query it live.
- **Handoffs:** the orchestrator detects a key moment, attaches the analytics context, then Moments explains why and
  Persona shapes it. Commentary is Narrator, then Persona. The Stats agent writes a periodic insight and owns the
  function tools. See [docs/architecture.md](docs/architecture.md).
- **Never blocks the broadcast:** every line and card is rendered immediately from deterministic templates in all five languages.
  When Foundry is configured, LLM calls run **concurrently in the background** and stream
  `commentary_update` and upgraded `moment_card` events as they finish, so slow model calls never make the
  replay lag.
- **Recovery:** each agent call has a timeout (`LLM_TIMEOUT_S`: 20 seconds from `Settings.from_env()`, 8 seconds on the Container Apps deploy) and `LLM_RETRIES` retries (default 1). If they all fail, a minimal **safe template**
  is used. Every step is emitted as an `agent_trace` (`ok` / `recovered` / `fallback`, attempts, latency) and
  shown in the UI's agent strip.
- **Fault injection for demos:** `ECHO_FAULT_AGENTS=narrator` makes the first call fail so you can watch the
  retry; `narrator!` makes every call fail so you can watch the fallback.

## Microsoft technology used

| Technology | How |
|---|---|
| **Microsoft Foundry** | `gpt-5-mini` deployment for Stats, Moments, Narrator, Persona and the Narrator's recap agent (`echo-recap`), via the Foundry project endpoint |
| **Microsoft Agent Framework** | `Agent`, `FoundryChatClient`, Python function tools; multi-agent orchestration with handoffs |
| **Azure Container Apps** | Live deployment (UAE North, 0.5 vCPU / 1 GiB, scale 0–1), keyless Foundry access and image pull via a user-assigned managed identity with the `Cognitive Services User` role (`Dockerfile`, `infra/deploy_aca.sh`), managed identity for keyless Foundry access, external ingress for SSE |
| **Azure Container Registry** | Cloud image build (`az acr build`), or a local docker/podman build when `LOCAL_BUILD` is set (`infra/deploy_aca.sh`) |
| **GitHub Copilot** *(planned)* | Planned for upcoming development work; this row will be updated once it is used |
| **GitHub Actions** | CI: tests, determinism check, Docker build and smoke test (`.github/workflows/ci.yml`) |

## Languages

English, Arabic (full RTL), Spanish, French and Portuguese, chosen for the Premier League's biggest
non-English fan bases (MENA, Latin America and Spain, France and francophone Africa, Brazil and Portugal).
Each language has its own commentator-style prompt (`agents/specialists.py`), native offline templates
(`agents/templates.py`, `agents/templates_intl.py`) and a language guard that rejects mixed-language replies so
the orchestrator retries or keeps the template. Player and club names stay as given in every language.

![Foundry ES](docs/ui_foundry_es.png)

## Public-URL spend guard

`app/budget.py` decides per viewer stream whether Foundry may be used: at most 6 AI streams per client per hour,
150 per UTC day (about $1.50 worst case) and 4 at the same time. Over a limit, the stream silently falls back to
the offline agents, so the demo keeps working and the credit cannot be burned. All limits are environment variables.

## Synthetic data

- **The generator** is a possession-chain simulator in `generator/core.py`.
  - Pass success depends on distance, pressure and the final third; overall completion is about 78%.
  - Shots run about 9–17 per team. xG comes from a logistic model on distance and goal angle, and goals are sampled from xG.
  - Momentum follows a random walk, and there is a soft cap on shot imbalance.
  - Each match has two scripted dramatic moments (a wonder save and a late big chance) that start from the real ball position.
- **Pitch:** coordinates are in metres on 105×68. Home attacks toward x=105 in both halves.
- **Schema:**
  - Events: `match_id, event_id, period, minute, second, team, team_name, player_id, player_name, type, x, y, end_x, end_y, outcome, speed_kmh, pressure_level, xg`.
  - Metadata: teams, 4-3-3 lineups, venue, kickoff and final score.
- **Demo matches:** `python -m generator --demo --out data/` gives three typical matches (seeds 53, 58, 63; 1-1, 3-1, 1-2).
  The output is deterministic, and CI checks this.
- **No real data:** there is no real Premier League data, footage, club or player name anywhere (Rules §4.7).

## Run it

Needs Python 3.11+. Offline mode makes no Azure calls, and it needs no `.env`. The demo matches in `data/` are already in the repo, so the generator line is optional.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m generator --demo --out data/               # optional: data/ is already included
LLM_MODE=offline uvicorn app.main:app --port 8000
# open http://localhost:8000 and press Kick off
# deep link (autoplay honours start=; Kick off and Restart always begin at 0'):
# /?match=EP-2026-002&speed=60&start=82&club=home&lang=ar&persona=analyst&autoplay=1
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
$env:LLM_MODE="offline"
uvicorn app.main:app --port 8000
# open http://localhost:8000 and press Kick off
```

**With Microsoft Foundry** (copy `.env.example`):

```bash
az login
export LLM_MODE=foundry
export FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
export FOUNDRY_MODEL=gpt-5-mini
uvicorn app.main:app --port 8000
```

**Docker and Azure Container Apps:**

```bash
docker build -t echo-pitch . && docker run -p 8000:8000 echo-pitch
AZ_ACR=<unique-name> ./infra/deploy_aca.sh     # see the header of the script for all variables
```

### Measured on Microsoft Foundry (gpt-5-mini, Global Standard)

A full replay of EP-2026-002 at 60× was run in English (fan) and Arabic (analyst) at the same time. The script
is `scripts/foundry_eval.py` and the raw results are in `docs/foundry_eval.json`.

| | EN | AR |
|---|---|---|
| LLM calls per match | 35 | 35 |
| LLM latency, p50 / p95 | 2.8 s / 3.9 s | 2.7 s / 4.3 s |
| Replay lag (event arrival vs schedule) | 1.01 s max | 1.00 s max |
| Tokens in / out | 17.1k / 2.7k | 17.0k / 3.3k |
| Cost per match per viewer stream | about $0.010 | about $0.011 |
| Agent failures | 0 | 0 |

The cost uses gpt-5-mini list prices of $0.25 per 1M input and $2.00 per 1M output tokens.

Cost controls:
- Only key moments, periodic insights and the recap go to the model.
- `reasoning.effort=minimal`.
- Output tokens are capped: 200 for a line, 400 for a moment or insight, 500 for the recap.
- No temperature parameter is sent.
- Persona context is folded into each prompt instead of an extra call.
- A language guard retries any reply in the wrong language.

Live test: `ECHO_FOUNDRY_IT=1 python -m pytest tests/test_foundry_integration.py`.

![Foundry EN](docs/ui_foundry.png)

### API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/matches`, `/api/matches/{id}/meta`, `/api/matches/{id}/events?upto=N` | data |
| GET | `/api/matches/{id}/stats?upto=N` | full analytics snapshot |
| POST | `/api/replays` `{match_id, speed 10–60, start_minute}` | start a replay |
| GET | `/api/replays/{rid}/stream?persona=&lang=en\|ar\|es\|fr\|pt&club=&player=&from_now=` | SSE agent stream (spend guard may switch it to offline agents) |
| GET | `/api/replays/{rid}/state` · DELETE `/api/replays/{rid}` | live state, stop |
| GET | `/api/config`, `/api/health` | mode, liveness |

## Testing

```bash
LLM_MODE=offline python -m pytest -q
```

68 tests pass offline. Two live Foundry tests stay skipped unless `ECHO_FOUNDRY_IT=1`:
- **generator:** schema, time ordering, goals match the scoreline, realism ranges, determinism, ball continuity, unique names, the shot cap, the CLI;
- **analytics:** bounds, monotonic xG, stoppage-time windows, momentum smoothing;
- **agents:** all five languages (template coverage, offline runs, the language guard), persona differences, the overlay schema, retry and recovery, forced fallback, environment defaults, the Foundry code path with stand-in agents, LLM calls not blocking the replay, building the Foundry agents;
- **API and SSE:** endpoints, validation, the Arabic stream, the spend guard (including its defaults), the UI being served.

`python scripts/screenshot.py` captures `docs/ui.png` with headless Chrome (needs Playwright).

## Repository layout

```
generator/   synthetic match generator (CLI: python -m generator)
analytics/   deterministic stats + explainability (agent tools)
agents/      config, Foundry/Agent Framework wiring, specialists, EN/AR/ES/FR/PT templates, orchestrator
app/         FastAPI: data API, replay service, SSE stream, static UI
web/         single-page broadcast UI (vanilla JS)
infra/       Azure Container Apps deploy script
docs/        architecture, demo video script, pitch, submission checklist, screenshots
tests/       pytest suite
```
