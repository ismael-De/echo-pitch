# Demo video script (target 1:50, hard limit < 2:00)

> **Draft for Ismael to rewrite in his own words.** Judges spot generic AI-written scripts; keep the structure,
> change the sentences. Record the real app running (no slides). Clear audio matters more than fancy editing.
> Upload to YouTube as **Public** at least a day before the deadline.

| Time | On screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:10 | Close-up of a plain stat graphic, then cut to Echo Pitch | "Broadcasts tell you *what* happened: 0.41 xG, 52% possession. Almost nobody tells you *why it matters*, or tells it your way." |
| 0:10–0:20 | Pick EP-2026-002, press Kick off | "Echo Pitch is a team of AI agents that turns a live stream of synthetic match events into commentary and explanations, personalised for every viewer." |
| 0:20–0:45 | Ticker filling, pitch drawing attacks, a goal banner | "Events stream in live. The Stats agent reads the numbers through function tools, the Narrator writes the line, and the Moments agent explains why this goal changes the game." |
| 0:45–1:00 | Point at a line switching TEMPLATE → LLM, then the agent bar and trace | "Every line appears instantly from a template, then upgrades to Foundry output a few seconds later. If an agent fails, the orchestrator retries and falls back, so the broadcast never stalls." |
| 1:00–1:20 | Switch to Arabic, then Analyst, favourite club + player | "One click and the same match is told in Arabic, for an analyst instead of a casual fan, around my club and my favourite player." |
| 1:20–1:35 | Quick architecture view (README mermaid) + eval table | "It runs on Microsoft Foundry with gpt-5-mini and Microsoft Agent Framework, at about one cent per match per viewer, with tests and CI on GitHub." |
| 1:35–1:50 | Full-time recap modal, end card with repo URL | "At full time, an automatic recap. Echo Pitch: every match, explained, for every fan." |

Checklist before recording: offline-free (`LLM_MODE=foundry`), browser zoom 100%, notifications off,
speed 60×, start at minute 78 of EP-2026-002 so a goal lands in the first 30 seconds.
Only mention GitHub Copilot if it was actually used in the repo.
