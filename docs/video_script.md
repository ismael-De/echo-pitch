# Echo Pitch: demo video script (target 1:50, hard limit < 2:00)

**Format:** 1920×1080 screen recording with English voice-over. Add burned-in captions; judges may watch muted.
No copyrighted music (use silence or a royalty-free track) and no real club or league logos.

**Setup before recording**
- `LLM_MODE=foundry` with a working Foundry deployment, or `offline` with the badge visible. Be honest on screen about which mode is showing.
- Browser at 1600×1000, zoom 100%, extra tabs closed.
- Pre-open these deep links:
  - A: `/?match=EP-2026-002&speed=30&start=44&club=home&autoplay=1`
  - B: `/?match=EP-2026-002&speed=60&start=84&club=home&player=<Saltmarsh #9 id>&autoplay=1`
  - C: the same as B with `&lang=ar&persona=analyst`
- For the recovery shot, restart the server with `ECHO_FAULT_AGENTS=narrator`.

| Time | Shot (screen) | Voice-over |
|---|---|---|
| 0:00–0:10 | Title card: "Echo Pitch: every match, explained, for every fan", then a fast cut to the live UI | "Football stories don't end with the scoreline. Echo Pitch turns raw match events into stories every fan can follow." |
| 0:10–0:25 | Link A: events flowing on the pitch map, the scoreboard ticking, commentary appearing | "We stream synthetic match events. Passes, shots, tackles and pressure come in live, and four AI agents on Microsoft Foundry read them as they happen." |
| 0:25–0:42 | Zoom on the momentum chart and the controlled/chaotic chip. A pressing-surge card appears. | "The Stats agent computes possession, xG, pass difficulty and momentum, all deterministic and never invented. The Moments agent explains *why* a spell matters: here, a pressing surge that turned the game chaotic." |
| 0:42–1:00 | Link B: the late goal, with the goal banner overlay and a GOAL card whose "why" text is highlighted | "When a goal goes in, we don't just say 'goal'. Late winner, against the run of play, from a 0.44 xG chance, so a comeback is now unlikely. Every overlay is a timed JSON card a broadcast graphics engine can render." |
| 1:00–1:15 | Toggle Fan → Analyst, then EN → عربي. The layout flips right-to-left and the same moment is re-told. | "The Persona agent personalises everything. The same moment becomes a precise analyst note or a fan's celebration, in English or Arabic, around your club and your player." |
| 1:15–1:30 | Pick a favourite player: ★ tags follow him on the pitch, and a speed alert pops up | "Pick a player and the broadcast follows him: name tags on every touch and speed alerts when he breaks clear." |
| 1:30–1:42 | Agent strip: narrator shows **recovered** in amber; the trace line reads "narrator → recovered (2 attempts)". A quick cut to the architecture diagram in the README. | "It's built with Microsoft Agent Framework: Stats, Moments, Narrator and Persona share one match state, hand off to each other, retry failures and fall back to safe templates, so the broadcast never stalls." |
| 1:42–1:50 | Full-time recap modal, then an end card: GitHub URL, "Microsoft Foundry · Agent Framework · Azure Container Apps" (add GitHub Copilot only if it was actually used) | "At full time, an automatic recap and player of the match. Echo Pitch: every match, made for every fan." |

**Edit checklist**
- Total runtime 1:45–1:55.
- Captions on.
- The mode badge is legible in at least one shot.
- The GitHub URL is readable for at least 3 s.
- Upload as Public or Unlisted to YouTube and paste the link in the submission.
