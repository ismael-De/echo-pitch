# Echo Pitch: submission pitch

## One-liner
Echo Pitch is a multi-agent match storyteller that turns live football events into explainable, personalised
commentary, moment cards and broadcast-ready overlays, in English, Arabic, Spanish, French and Portuguese.

## Elevator pitch (about 150 words)
Broadcast data tells fans *what* happened, but rarely *why it matters*, and everyone gets the same feed.
Echo Pitch ingests a live stream of synthetic match events and runs four specialist agents, built with
**Microsoft Agent Framework** on a **Microsoft Foundry** model:
- **Stats** grounds everything in deterministic metrics (xG, pass difficulty, pressing, momentum).
- **Moments** explains why a moment matters (game state, run of play, control vs chaos).
- **Narrator** writes live commentary and recaps.
- **Persona** reshapes it for an analyst or a casual fan, a favourite club or player, in English, Arabic, Spanish, French or Portuguese.

A fifth agent, the deterministic **Verifier (Guard)**, checks every number and name against the match facts
before anything is shown. A rejected draft goes back to its writer once, and every line carries its evidence.
In a measured eval, 4 of 476 planted errors in real gpt-5-mini lines got through, and 0 unverified lines were shown.
The agents share one match state, hand off to each other, retry failures and fall back to verified templates, so
the broadcast never stalls. Commentary is spoken with **Azure AI Speech** neural voices in all five languages,
and there is an audio-first mode for blind fans. The output is timed, machine-readable overlay JSON plus a live web experience.
It runs live on **Azure Container Apps** (https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io). The result is the same match
intelligence, made for every fan.

## What we built
- A seeded synthetic football event generator (about 1,900 events per match, xG-consistent goals, dramatic moments).
- A deterministic analytics layer exposed to the agents as function tools.
- A multi-agent orchestrator. Commentary is Narrator then Persona. A key moment is Moments then Persona.
  Stats owns the numbers. Shared state, async LLM upgrades, retries and fallbacks.
- An SSE replay API and a broadcast-style web UI: pitch map, overlays, momentum, Analyst/Fan, EN/AR/ES/FR/PT (RTL for Arabic).
- A Verifier (Guard) agent with evidence footnotes in the UI, and a measured eval (`docs/EVAL.md`): planted errors, false rejections, LLM-as-judge groundedness 4.77/5, latency.
- An MCP server (`/mcp/` + stdio) exposing the stats and the Verifier. A Foundry Agent Framework agent and GitHub Copilot CLI both used it.
- Spoken commentary (Azure AI Speech: en-GB, ar-SA (ar-JO optional), es-ES, fr-FR, pt-BR neural voices) and an audio-first accessible mode.
- An optional producer-approval mode and a per-replay audit log of every verdict and decision.
- A Docker image, an Azure Container Apps deploy script and GitHub Actions CI.

## Problem it solves
Personalised, explainable, multilingual match storytelling at broadcast speed, without hand-written graphics
or commentary for every audience.

## Microsoft and Azure technology
Microsoft Foundry · Microsoft Agent Framework (incl. `MCPStreamableHTTPTool`) · Azure AI Speech · Model Context
Protocol · Azure Container Apps · Azure Container Registry · Managed Identity · GitHub Actions · GitHub Copilot CLI
(wrote the Verifier test suite and a narrator fallback test, and was used as an MCP client)

## Category
Primary: **Best Multi-Agent System**. Also relevant: Best Use of Microsoft Foundry.
