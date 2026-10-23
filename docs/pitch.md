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

The agents share one match state, hand off to each other, retry failures and fall back to safe templates, so
the broadcast never stalls. The output is timed, machine-readable overlay JSON plus a live web experience.
It runs live on **Azure Container Apps** (https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io). The result is the same match
intelligence, made for every fan.

## What we built
- A seeded synthetic football event generator (about 1,900 events per match, xG-consistent goals, dramatic moments).
- A deterministic analytics layer exposed to the agents as function tools.
- A multi-agent orchestrator. Commentary is Narrator then Persona. A key moment is Moments then Persona.
  Stats owns the numbers. Shared state, async LLM upgrades, retries and fallbacks.
- An SSE replay API and a broadcast-style web UI: pitch map, overlays, momentum, Analyst/Fan, EN/AR/ES/FR/PT (RTL for Arabic).
- A Docker image, an Azure Container Apps deploy script and GitHub Actions CI.

## Problem it solves
Personalised, explainable, multilingual match storytelling at broadcast speed, without hand-written graphics
or commentary for every audience.

## Microsoft and Azure technology
Microsoft Foundry · Microsoft Agent Framework · Azure Container Apps · Azure Container Registry · Managed
Identity · GitHub Actions (GitHub Copilot planned)

## Category
Primary: **Best Multi-Agent System**. Also relevant: Best Use of Microsoft Foundry.
