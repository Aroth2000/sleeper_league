# Sunday Scaries Skill — What It Is and How To Use It

Everything for the skill is written. This file explains what got built, how to get it working, and what it can't do yet.

---

## What the skill actually is

`sunday-scaries.skill` is a single file (a zip archive under the hood, ~180 KB) containing three things:

**1. The instructions — `SKILL.md`.** An operational runbook, not a description. It tells Claude the exact order of operations: orient → fetch → build state → run the workflow → write outputs. It includes branch logic for what to do when state is missing, stale, degraded, or already generated this week.

**2. Seven reference files**, read on demand rather than loaded up front, so the skill stays cheap to invoke: `league.md`, `scoring.md`, `teams.md`, `keepers.md`, `season_phases.md`, `data_layer.md`, `output_format.md`.

**3. The entire working system, bundled.** This is the important part — the zip carries the actual code and data, not just instructions pointing at them:

| Bundled | What it is |
|---|---|
| `league_config.json` | Every league constant, hand-verified against the Sleeper API |
| `players_cache.json` | All 222 rostered players resolved to name/position/team |
| `state_builder.py` | Turns raw Sleeper JSON into a structured weekly state file |
| `players_cache.py` | Incremental player-identity cache with CLI |
| `analysis/` | Opponent pressure, waiver contention, keeper equity, exact league scoring, plus a full test suite |
| `weekly.js` | The 18-agent weekly workflow |
| `fetch_manifest.md` | The contract between the WebFetch step and the builder |
| `state/week_0.json` | A real preseason baseline state file (~59 KB) |
| `raw/` | Live-fetched league, rosters, users, and all 160 of last year's draft picks |
| `docs/` | The design plan and the league reference doc |

That bundling is deliberate. It means a brand-new chat, months from now, in a fresh container with nothing on disk, can rebuild the whole system from the one file you kept.

---

## How to get it

**I can't install it into your account myself.** Skills on this container's disk are a read-only cache — writing files there doesn't create a skill in your account, and this container gets wiped when the session ends. What I can do is hand you the file.

So: I'm delivering `sunday-scaries.skill` to you in this conversation. Depending on how your organization's settings are configured, you may get an option to save it as a skill when you receive it. If that option appears, saving it makes `/sunday-scaries` available in any future chat. If it doesn't appear, the file still works — see the fallback below.

I have no way to see whether it saved on your end, so treat it as delivered rather than installed until you've confirmed it yourself.

**Fallback if saving isn't available:** keep the `.skill` file somewhere you can find it (email it to yourself, drop it in your files). Any future session, attach it and say "unzip this and follow SKILL.md." Everything needed is inside. That's slightly more friction than a slash command but functionally identical.

---

## How to use it once it's available

**The full Tuesday run** — say `/sunday-scaries` or just "run my Tuesday update." It fetches fresh Sleeper data, rebuilds state, fans out 18 agents (nine opponents, four news sweeps, free-agent pool, your team, then the waiver contention model and trade board, then synthesis), and returns an eight-part brief: action card, lineup card, ordered waiver claims with probabilities, drop candidates, trade board, opponent intel, keeper-equity watchlist, and an updated state file.

**Quick questions don't trigger the full run.** The skill has explicit cost-aware escalation built in, which I think is the best thing about how it turned out. Ask "who should I start?" and it fetches rosters, rebuilds state, and reasons over your lineup inline — no 18-agent fan-out. Ask "should I claim this guy?" and it verifies he's genuinely a free agent against all ten rosters, then weighs win-now value against his 12th-round keeper equity and who picks ahead of you. It only escalates to the full workflow when the question is "what should I do this week" or when the answer depends on modelling what rivals will do.

**Ask it anything about the league.** Keeper decisions, trade evaluations, opponent scouting, "what changed this week" — it has the whole reference set.

---

## Guardrails it enforces

These are non-negotiable in the skill, because each one corresponds to a way this project actually went wrong at some point:

- **Availability gate.** It will never recommend a free agent without first confirming against all ten rosters that he's actually unrostered. A confidently-recommended player who's already on someone's bench wastes a claim.
- **Freshness gate.** Every injury, snap, practice, or role claim must cite a named source dated within seven days. This exists because one section of the draft research came back built on Wikipedia rather than live beat coverage and had to be redone.
- **Files are canonical, not the chat.** It reads state from disk, never from memory of a previous conversation.
- **Diff, don't snapshot.** The value is in what changed since last week, not in re-deriving the world.

---

## Known gaps — read this before Week 1

The build agents were explicitly instructed to flag gaps rather than paper over them, and they did. In priority order:

**2026 bye weeks are not populated.** No Sleeper endpoint exposes them, and the agent deliberately refused to fill them in from memory, on the reasoning that a wrong bye week silently produces a zero-point starter — worse than an admitted gap. `bye_coverage` returns `status: "unknown"` until the 32-team map is hand-entered into `league_config.nfl_bye_weeks_2026`. **This blocks real bye analysis from around Week 4**, and it's a ten-minute fix once byes are published. It's the single biggest remaining item.

**The matchups code path has never run against live data.** The league is still pre-draft, so no `/matchups` payload exists yet. The field mapping is written to Sleeper's documented shape but is unverified. Check it in Week 1 before trusting any performance-pressure numbers.

**104 rostered players still carry August 2025 team data.** Your twelve were refreshed; the other nine rosters are queued. This is exactly the bug that made Mike Evans read as a Buccaneer when he'd signed with San Francisco. Surfaced by `players_cache.py stale`.

**WebFetch transcribes JSON through a small model**, so it isn't guaranteed lossless. One confirmed slip is already pinned in an overrides table (Hunter Henry came back as a WR rather than a TE). Load-bearing values should be spot-checked.

**Four league settings are still unconfirmed** and are tracked in `league_config.open_questions`: whether waivers are rolling priority or FAAB (these imply completely different claim strategies), the waiver processing clock time, whether FLEX is really 2 slots or 1, and whether the DEF scoring fix was applied. The system produces both answers where the waiver ambiguity matters rather than silently picking one.

---

## Status of the rest of the build

All seven implementation agents are done, including the adversarial integration test and the real-browser Playwright UI test. Both found and fixed genuine bugs rather than rubber-stamping self-reports — including a structural one (the weekly flow was overwriting the deterministic state file with model output every week; fixed with a new `system/merge_state.py`) and two real mobile UI bugs (an off-screen active tab after a deep link, and text that failed contrast standards). Both dashboard fixes have been applied to the generator itself (`build_dashboard.py`), not just the one-off output, and re-verified with the full 61-check Playwright suite after regenerating.

The one substantive gap called out by the tester: `weekly.js` doesn't yet call the deterministic `analysis/*.py` modules, so the availability gate currently runs as a prompt instruction rather than code. That's a deliberate open design decision, not a bug — full detail in `IMPLEMENTATION_LOG.md`.

Full reports: `system/TEST_REPORT.md` (integration) and `system/ui/UI_TEST_REPORT.md` (UI).
