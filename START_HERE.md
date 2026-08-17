# Start here

This repo is the canonical home for the Sunday Scaries fantasy football system — code, data, and
the full research/decision history. It was built across a long Cowork conversation; this file
exists so that conversation becomes optional to read, not required. If you're a fresh Claude
session or a future version of Andrew picking this up cold, everything you need is below or one
link away.

**Repo:** github.com/Aroth2000/sleeper_league
**League:** Sunday Scaries, Sleeper league_id `1389753893356838912`, 10-team superflex, half-PPR +
0.5/first-down, keeper league, 3rd season (2026).
**Owner:** Andrew Roth (andrew.roth32@gmail.com), Sleeper handle `andrewroth32`, roster_id 2,
**drafting from slot 8** (confirmed, see `docs/league_reference.md` §8).

---

## Written for two audiences

Everything below Part 1 is split into **Part 2 (for Andrew)** and **Part 3 (for whichever Claude
session picks this up next)**. Read your part; skim the other if curious.

---

## Part 1 — What's true right now (read this regardless of who you are)

**Status as of Aug 17, 2026:** the code and continuity architecture are built and verified. The
repo has not been pushed to GitHub yet — that's the one manual step still outstanding, because the
Cowork session that built this doesn't have push rights to it (see the gotcha in Part 3). If you're
reading this file *from* GitHub, that step is done and this line is stale — ignore it.

**What's proven, by execution, not just claimed** (see `docs/IMPLEMENTATION_LOG.md` and
`system/LOOP_VERIFICATION_REPORT.md` for the actual evidence):
- The data layer (`system/state_builder.py`, `system/players_cache.py`) — 222/222 players resolved,
  runs clean against real Sleeper data, degrades gracefully on missing/corrupt input.
- The analysis modules (`system/analysis/*.py`) — 76 tests passing, real bugs found and fixed
  during verification (not just written and assumed correct).
- The weekly workflow (`system/weekly.js`) — 18 agents, verified with the AsyncFunction harness
  method (not `node --check`, which is proven unreliable for this file — see
  `system/weekly_README.md`).
- The continuity loop (`system/repo_sync.py` + the rewritten `system/skill/SKILL.md`) — proven to
  actually carry state week-to-week by simulating two consecutive runs against a real clone.
- The deterministic analysis wiring (`system/analysis/build_analysis_output.py`) — the availability
  gate and pressure model now run as code the LLM cites and refines, not a prompt the LLM has to
  get right from memory.

**What's still open** (tracked, not forgotten — see `docs/SKILL_README.md`'s "known gaps" and
`docs/league_reference.md`'s open questions):
- 2026 NFL bye weeks aren't populated (no Sleeper endpoint exposes them; deliberately not guessed).
- ~104 rostered players outside Andrew's 12 still carry Aug-2025-vintage team/injury data.
- Waiver processing clock time, DEF scoring fix, keeper deadline — unconfirmed league settings.
- The live website/dashboard idea is explicitly parked, not abandoned — see `docs/storage_proposals.md`.
- The Tuesday scheduled task (`trig_019bKuypi5thgjp2sGkYArBf`, fires Tuesdays ~12:00 UTC) still
  runs the *old* flow (restore from the skill's bundled snapshot) — it has NOT been updated to use
  `repo_sync.py` and pull from this repo yet. That's intentional: updating it before the repo was
  even pushed would have risked breaking a real Tuesday run. Updating it is the next real task once
  the push is confirmed and one live run has been sanity-checked.

---

## Part 2 — For Andrew

**The one thing you actually need to do:** push this repo. You were handed
`sleeper_league_repo_ready_to_push.tar.gz` — it has 2 real commits and everything below already in
it. From any machine with git: `tar -xzf sleeper_league_repo_ready_to_push.tar.gz -C sleeper_league
&& cd sleeper_league && git push -u origin main`. That command will use whatever git auth already
exists on that machine — it has nothing to do with the Cowork sandbox issue that blocked me.

**After that, this repo — not any specific chat — is the source of truth.** You can close this
Cowork conversation without losing anything; everything of substance that came out of it is either
in `system/` (the runtime) or `docs/` (the research and decision history), both now inside this
repo. The one exception: this specific conversation's back-and-forth (why we made each call) isn't
preserved verbatim, but the *outcomes* of that back-and-forth are all written down in `docs/`.

**Starting a new session against this repo, later:** whether it's a new Cowork chat, a session at
claude.ai/code, or Claude Code on your own machine, the move is the same — give it access to this
repo and say "read START_HERE.md." It should not need anything else from you to get oriented. If it
asks you something this file doesn't answer, that's worth flagging back to me (well, to whichever
Claude you're talking to) as a real gap in this document, not just answering it inline and letting
the doc go stale again.

**Decisions already made — don't relitigate these without a reason:**
- Draft slot 8, full 10-team draft order confirmed (`docs/league_reference.md` §8).
- Keepers: Kenneth Walker III (R4), Bo Nix (R12), Jameson Williams (R14) — see
  `docs/league_reference.md` for the reasoning, `docs/draft_board_2026.md` for the pick-by-pick plan.
- Architecture: code + weekly data both live in this one repo, not split across Drive/GitHub — see
  `docs/storage_proposals.md` for why. The live-website idea was explicitly deprioritized, not
  rejected.
- Continuity mechanism: the repo itself (via `repo_sync.py`) is the "memory" between Tuesday runs,
  not session continuity, which doesn't exist for scheduled tasks — see `docs/weekly_loop_closure_plan.md`.

**Open decision still waiting on you:** whether the Tuesday scheduled task should hold its own
push credential for full automation, or whether pushing stays a manual/desktop step — this was
flagged in `docs/weekly_loop_closure_plan.md` Phase 2 and never fully resolved given how the push
mechanics turned out to be more restrictive than expected. Worth revisiting once you've done the
first manual push and seen how much friction it actually is.

---

## Part 3 — For a fresh Claude session

You have no memory of the conversation that built this. Everything you need is in this repo. Do
not assume anything about league facts, code behavior, or decisions from training data or guessing
— it's all written down, read it.

**Orientation order:**
1. This file.
2. `system/skill/SKILL.md` — the actual operational runbook, if you're being asked to run a weekly
   brief or answer a fantasy question.
3. `docs/league_reference.md` — league facts, scoring, keepers, team directory.
4. `docs/IMPLEMENTATION_LOG.md` and `system/LOOP_VERIFICATION_REPORT.md` — what's been built and
   verified, and how, in detail.
5. Anything else in `docs/` on demand — it's organized by topic, not meant to be read front to back.

**Before trusting anything runs, verify it yourself — this project's established standard, learned
the hard way multiple times (see `system/TEST_REPORT.md`, `system/ui/UI_TEST_REPORT.md`,
`system/LOOP_VERIFICATION_REPORT.md` for the receipts):**
```bash
cd system
python3 state_builder.py --dry-run --summary          # should print real standings, Andrew's lineup
python3 players_cache.py stats                          # want 222/222 resolved, 0 unresolved
cd analysis && python3 test_analysis.py                 # want 76 tests, all passing
```
If any of those look different from what's described here, something changed or broke since this
was written — don't assume the docs are still accurate, re-verify and update them.

**Hard environment constraints — verified repeatedly across this project, don't rediscover them the
expensive way:**
1. The Sleeper API is unreachable from Python/curl/bash in a Cowork-style sandbox (403 on CONNECT
   to `api.sleeper.app`) — only the WebFetch tool reaches it. If you're in a different kind of
   session (e.g. Claude Code CLI on Andrew's own machine) this constraint may not apply — check
   before assuming.
2. `node --check` does **not** reliably validate `system/weekly.js` — it can pass on a broken file.
   Verify it by rebuilding the function body the way the Workflow runtime does (documented in
   `system/weekly_README.md`), not with `node --check`.
3. **The git-push gotcha that blocked this repo's first push, so you don't repeat it:** in an
   Anthropic-hosted cloud sandbox, `git push` only works against a repository that was explicitly
   attached to the session at creation — a general-purpose Cowork conversation (like the one that
   produced this repo) does NOT get push rights just because the user connected their GitHub
   account. If you need to push and get the same "not in this session's authorized repository set"
   403, you're very likely in that situation — the fix is not a token, it's running in a session
   type that was actually started against this repo (a proper `claude --cloud` / claude.ai/code
   session with this repo selected, or a local checkout), or having Andrew push manually / via his
   own machine's git.
4. Usage caps can interrupt long multi-agent runs. If you're using the Workflow tool for anything
   substantial, log the run ID somewhere in `docs/IMPLEMENTATION_LOG.md` immediately after starting,
   before it might get interrupted — that's the pattern this whole project has relied on to survive
   cap hits without losing work.

**If asked to change code:** read the relevant file fully first, make the change, verify it by
actually running it (not by reading it and asserting it's correct), then commit with a message that
explains *why*, and push if your session has the rights to. If it doesn't, tell Andrew exactly what
changed and that it needs a push from a session/machine that has access — don't silently leave
local-only commits without saying so.

**If asked to run the weekly Tuesday brief:** follow `system/skill/SKILL.md` exactly, in the order
it specifies (as of this writing, Step 0 through Step 5 — pull the repo first, don't skip
`merge_state.py`, never write model output straight into `week_N.json`). Check whether the
scheduled task's stored prompt has actually been updated to this flow yet (see Part 1 above) — if
it's still the old bundle-restore flow, say so rather than silently assuming continuity works.
