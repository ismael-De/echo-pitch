# Demo video script (target 1:50, hard limit < 2:00)

> **Draft for Ismael to rewrite in his own words.** Judges spot generic AI-written scripts; keep the shots,
> change the sentences. Record the real app (no slides except the short README cut). Clear audio matters more
> than fancy editing. Say **Multi-Agent** once. Upload to YouTube as **Public** well before
> Wednesday 28 Oct 2026, 09:59 Asia/Amman (UTC+3).

Open each live shot from its URL and let `autoplay=1` start it. **Kick off** and **Restart** always start at
minute 0, so do not press them on these links. The match menu shows **Saltmarsh FC v Brackenridge Town**.
Speed on these URLs is **60** (the control defaults to 30). The badge reads **Azure AI Foundry** once the
stream connects. Warm the live site first: a cold start is about 20 seconds.

| Time | On screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:10 | A plain stat, then Echo Pitch. Badge reads **Azure AI Foundry**. | "Broadcasts tell you *what* happened: 0.41 xG, 52% possession. Almost nobody tells you *why it matters*, or tells it your way." |
| 0:10–0:35 | URL `/?match=EP-2026-002&speed=60&start=72&autoplay=1`. About 13 seconds in, the clock shows **86'** and the banner reads **GOAL! Pavel Garrow · 2-1**. Footer pills: Stats → Moments → Narrator → Persona. Cut away before about 20 seconds, when the full-time modal appears. | "Echo Pitch is a multi-agent system. Events stream in live. Stats reads the numbers through function tools, Narrator writes the line, and Moments explains why this goal changes the game." |
| 0:35–0:50 | In that goal shot, a commentary chip fades from **TEMPLATE** to **LLM**. The Narrator pill is green. The trace looks like `86' narrator.goal → ok · llm · …ms`. | "Every line appears instantly from a template, then upgrades to Foundry output. The broadcast never waits on the model." |
| 0:50–1:05 | Two short local clips, pre-rolled, about five seconds each. Server restarted between them. `ECHO_FAULT_AGENTS=narrator`: Narrator pill amber, trace contains `recovered (2 attempts)` and `template`. Then `ECHO_FAULT_AGENTS=narrator!`: pill red, trace contains `fallback (2 attempts)` and `safe_template`, and the chip stays **SAFE_TEMPLATE**. | "If an agent fails, the orchestrator retries. If it still fails, a safe template takes over, and the picture keeps moving." |
| 1:05–1:25 | New clip, fault variable unset: `/?match=EP-2026-002&speed=60&start=66&autoplay=1`. Language menu → **العربية**. The page flips right to left. The scoreboard and the ECHO PITCH wordmark stay left to right. The ticker clears and the new lines are Arabic. Click **محلّل**. Club reads النادي, Player اللاعب, the Agents label reads الوكلاء, and the four pill names stay English. The button reads **↻ إعادة**. Cut before full time, about 26 seconds in. | "One click and the same match is told in Arabic, for an analyst, around my club and my player." |
| 1:25–1:40 | README architecture diagram and the Foundry eval table (about one cent per match per viewer). | "It runs on Microsoft Foundry with gpt-5-mini and Microsoft Agent Framework, at about one cent per match per viewer, with tests and CI on GitHub." |
| 1:40–1:50 | URL `/?match=EP-2026-002&speed=60&start=88&autoplay=1`. About two seconds in, Luca Jessop, clock **90+1'**. About four seconds in, the modal **Full-time recap**: score, paragraph, moment chips, Close. After the modal, an editor card with the repo URL. | "At full time, an automatic recap. Echo Pitch: every match, explained, for every fan." |

Checklist before recording:

- Foundry take: `LLM_MODE=foundry`, a real project endpoint, `az login`. After the stream connects, the badge reads **Azure AI Foundry**. An offline run keeps the badge on **offline agents** and the chip on **TEMPLATE**.
- The live Azure app is the main take. Retry and fallback are local only: set `ECHO_FAULT_AGENTS`, restart uvicorn, record, then restart again with the variable cleared.
- Browser zoom 100%, notifications off.
- The README jump-in link uses `start=82` (the Pavel goal is about 4 seconds in). This script uses `start=72` for the goal shot so the banner lands about 13 seconds into that shot. Leave the README link as it is.
- Only mention GitHub Copilot if it was actually used in the repo.

## v2 video (27 Oct 2026, evening): `echo_pitch_demo_v2.mp4`, 1:44, TTS narration (en-US-AndrewNeural)

| Time | On screen | Narration |
|---|---|---|
| 0:00 | Title card | Echo Pitch is a multi-agent football storyteller on Azure AI Foundry. Version two makes every line verified, spoken, and accessible. |
| 0:10 | Live app, Analyst, 84' at 30×, 🛡 evidence footnotes opened | Four writer agents, built with Microsoft Agent Framework, stream live commentary, moment cards and overlays. A new fifth agent, the Verifier, checks every number and every player name against the match facts before anything is shown. Click the shield, and you see the evidence behind each claim. |
| 0:29 | "Measured, not claimed" card (docs/EVAL.md numbers) | We planted wrong numbers, scores and players into real gpt-5-mini lines … 472 of 476 were caught … zero unverified lines … groundedness 4.77 of 5 … wrong-team errors remain a known gap. |
| 0:50 | Live app in Arabic (RTL) + an Azure Speech clip in ar-JO-TaimNeural | Fans hear it too. Azure AI Speech neural voices speak all five languages, including a Jordanian Arabic voice. |
| 1:04 | Producer mode: a pending AI draft is approved, then the audit log | For broadcasters, producer mode holds AI rewrites for a human OK, and every verdict and decision lands in an audit log. |
| 1:16 | Copilot CLI calling the live MCP server | The stats and the Verifier are also an MCP server … rejects a false four-one scoreline. A Foundry agent uses the same tools. |
| 1:29 | Audio-first mode | Audio-first mode gives blind and low-vision fans large, high-contrast text, and speaks every line. |
| 1:37 | End card | Echo Pitch. Every match, explained, and verified, for every fan. |

The Arabic clip is a real `/api/tts` response from the live app. The browser recording itself has no audio.

### v3 (27 Oct 2026): `echo_pitch_demo_v3.mp4`, 1:46
- The raw JSON audit page (1:12–1:15 in v2) is replaced by a styled audit-log card. The card is rendered from a real `GET /api/replays/{id}/audit` response on the live app (15 verifier checks, 1 producer approval).
- The Arabic clip is a real Arabic commentary line from the live app ("يا لها من لحظة! Pavel Garrow يهزّ الشباك لـSaltmarsh FC! SHF 2-1 BRT"), spoken by `/api/tts`. The response header was `X-Voice: ar-JO-TaimNeural` (Arabic, Jordan). The text is Modern Standard Arabic, so it has a broadcast register, not a Jordanian dialect.
