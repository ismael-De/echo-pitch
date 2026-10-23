# Winning plan: Echo Pitch

Converted from the plan Page "خطة الفوز: Echo Pitch". It covers what Microsoft hackathon winners do, where we stand on the judging criteria, and a day-by-day plan up to the deadline: **Wed 28 Oct 2026, 9:59 AM Amman time (UTC+3)**.
Status marks: ✅ done (checked against the repo on 23 Oct) · ⬜ remaining.

## Key findings

> **Bottom line:** the video is the first thing a judge sees, and the docs must match the code exactly. In the AI Agents Hackathon 2025, winning teams were removed because their docs did not match the architecture or their code had not been tested.

1. The 1st-place winner, RiskWise (Supply Chain), solved a real business problem with a Next.js UI and agents on Azure AI Agent Service. Real-world impact counts as much as the tech.
2. Apollo (Best C#) had clearly named agents with clear roles (Athena, Hermes) that worked together, and the architecture was explained in detail. That is exactly what we want to show with our four agents.
3. Out of 570 projects, only 7 won categories. Judging covered innovation, impact, usability, solution quality and fit with the category, which are close to our criteria.
4. Devpost advice: open the video with one sentence about the problem, then show the app running live, with no slides. Write the script yourself, not with AI.
5. Judges say the story and the presentation are a big part of winning. The video, the description and the code must support each other.
6. Upload the video early and make it Public. Watch the audio: judges will accept a simple video, but not audio they can't hear.

## Judging criteria: where we stand (20% each)

| Criterion | Status | What's missing |
|---|---|---|
| Technological implementation | Strong | ⬜ a real GitHub Copilot edit (README still says "planned") · ✅ live Azure deployment |
| Agentic design & innovation | Strong | ⬜ show the agent strip, retry and fallback in the video |
| Real-world impact | Medium | numbers: ~1 cent per match per viewer (✅ in README), Arabic commentary for a 400M audience |
| UX & presentation | Medium | ⬜ story video · ✅ README with images + GIF · ✅ natural Arabic commentary |
| Category fit | Strong | ✅ Multi-Agent stated explicitly in the README · ⬜ say it in the video |

## Day-by-day plan

| Day | Grok Bot | Ismael |
|---|---|---|
| Thu 22 | ✅ Better Arabic, smooth commentary swap-in, RTL fixes | ⬜ Activate Innovation Studio in an Incognito window |
| Fri 23 | ✅ README with GIF, architecture diagram, eval results | ⬜ Try the UI and give feedback |
| Sat 24 | ✅ Azure Container Apps deployment (done early) | ⬜ A real GitHub Copilot edit |
| Sun 25 | ✅ Draft video script under 2 min (`docs/video_script.md`) with an Arabic "wow" moment | ⬜ Rewrite the script in his own words and rehearse |
| Mon 26 | ✅ Docs match the code (done early, 23 Oct) | ⬜ Record the video and upload it to YouTube as Public |
| Tue 27 | ⬜ Submission checklist and last fixes | ⬜ Make the repo public, fill in the submission form |
| Wed 28 | ⬜ Final confirmation | Deadline 9:59 AM; better to submit on Tuesday |

## Done so far

- ✅ Arabic commentary in a TV-commentator style, not a literal translation, with no English words (22 Oct)
- ✅ AI commentary replaces the template line with a smooth fade instead of a jump
- ✅ Arabic scoreboard fixed left-to-right; Latin names ordered correctly inside RTL text
- ✅ Tests pass (now 68 passed, 2 skipped offline); the live Foundry integration test passed
- ✅ README: animated replay GIF, category section (Multi-Agent + Foundry), table mapping each judging criterion to where it is
- ✅ Docs-vs-code review: fixed the gpt-4o-mini mention and the premature "deployed on Azure" claim
- ✅ Docs-vs-code audit (23 Oct): test count is 68 passed and 2 skipped, Narrator covers all five languages, timeout and env defaults, handoffs, and the ACR `LOCAL_BUILD` path
- ✅ New Foundry screenshots in English, Arabic and Spanish
- ✅ Video script draft (1:50) in `docs/video_script.md`; Ismael must rewrite it in his own words
- ✅ 5 languages (AR, EN, ES, FR, PT) with a language dropdown and tests
- ✅ Live on Azure: https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io
- ✅ Credit guard: 6 AI streams per visitor per hour, 150 per day, 4 at once, then offline templates
- ✅ Whole-number percentages in every language; new Arabic and recap screenshots
- ⬜ Make the repo public (Ismael, on the 27th): `gh repo edit ismael-De/echo-pitch --visibility public --accept-visibility-change-consequences`

## Sources

- [AI Agents Hackathon 2025: winners](https://microsoft.github.io/AI_Agents_Hackathon/winners/)
- [Category Winners Showcase (Microsoft Tech Community)](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/ai-agents-hackathon-2025-%E2%80%93-category-winners-showcase/4415088)
- [Why the winners changed (teams removed), GitHub Discussions](https://github.com/microsoft/AI_Agents_Hackathon/discussions/770)
- [6 tips for a winning demo video (Devpost)](https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video)
- [How to win a hackathon: 5 judges (Devpost)](https://info.devpost.com/blog/hackathon-judging-tips)
