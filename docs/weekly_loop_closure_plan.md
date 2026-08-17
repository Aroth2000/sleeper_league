# Plan: closing the gaps in the week-by-week loop

Scope note: the live website is explicitly out of scope for this plan — this is only about making
the Tuesday-to-Tuesday cycle actually connect to itself, and making the analysis inside each cycle
trustworthy rather than prompt-guessed. Nothing here has been executed. Everything downstream of
Phase 0 is blocked on the GitHub repo.

---

## The two gaps this closes

**Gap 1 — no memory between weeks.** Every Tuesday firing starts a brand-new, unrelated cloud
session (confirmed: the scheduled task has no persistent session tied to it). That session has no
automatic access to what last week's session wrote. Right now "continuity" only exists if the
skill's bundled snapshot happens to be current, which it stops being the moment one real week
passes. The design calls for "diff, don't snapshot" — right now it can't actually do that.

**Gap 2 — the availability gate and pressure model run as prompt instructions, not code.** The
integration tester's exact finding: `weekly.js` never calls `analysis/opponent_pressure.py`,
`waiver_contention.py`, or `keeper_equity.py` — zero grep matches. All 76 tests pass, the modules
work standalone, but nothing in the actual weekly run invokes them. The plan's hard rule ("the
availability gate belongs in deterministic code, not a prompt") is currently not true in practice.

Both gaps get closed by the same move: give the loop a durable place to read from and write to
*before* the LLM stage runs, instead of relying on either session continuity or LLM self-discipline.

---

## Phase 0 — Blocked on you

- GitHub repo (empty is fine, or pre-seeded, your call).
- A fine-grained personal access token scoped to just that repo, contents read/write. (Walked
  through in the previous message — happy to re-explain if you want it again when you're ready.)

Nothing below can execute until these land.

---

## Phase 1 — Repo bootstrap

Push what already exists, once, to establish the canonical layout:

```
sunday-scaries/
  system/                  <- everything currently in /home/claude/sunday_scaries/system/
    league_config.json
    state_builder.py
    players_cache.py
    players_cache.json
    analysis/
    weekly.js
    skill/
  data/
    week_00/  state.json                    <- today's real baseline, seeded now
    (week_01/, week_02/, ... appended by Phase 2 going forward)
  IMPLEMENTATION_LOG.md, weekly_system_plan.md, league_reference.md   <- process history, for context
```

`data/` is deliberately inside the same repo as `system/`, not a separate store — confirmed
earlier this is a fine pattern for a project this size, and it means one login, one history, one
thing to point the weekly run at.

**Output of this phase:** first commit, pushed. I verify by cloning it fresh into a scratch
directory and confirming `state_builder.py --dry-run` runs from that clone unmodified.

---

## Phase 2 — Rewire the loop for continuity

This is the actual fix for Gap 1. Changes to `SKILL.md` / the scheduled task's stored prompt:

**New Step 0 (before everything currently in Step 1):** clone or pull the repo into the working
directory. If the clone fails (auth problem, repo renamed, network), fall back to the skill's
bundled snapshot exactly as today and say so plainly in the brief — never fail silently.

**New Step 2.5:** after `state_builder.py` runs (as today, from fresh Sleeper data), diff it
against `data/week_{N-1}/state.json` *read from the repo clone*, not from local disk continuity.
This is the actual continuity fix — it doesn't matter that this is a brand-new container, because
the "memory" now lives in the thing we just cloned, not in session state.

**New Step 5 (after today's merge_state.py step):** commit `data/week_{N}/report.md`,
`state.json`, and `state.synthesis.json` and push. One commit per week, so `git log` alone becomes
a month-from-now index — no separate archive system needed.

**Open decision — how the unattended Tuesday session authenticates to push.** Two options, real
tradeoff, your call:

| | Stored token | Desktop sync |
|---|---|---|
| How | The fine-grained PAT lives in the trigger's stored prompt, used automatically every Tuesday | Cron delivers to chat as today; whenever you open the desktop app, I push using *your own* already-authenticated local git — I never hold a token |
| Fully unattended | Yes | No — depends on you opening the app periodically |
| Where the token lives | In the trigger config, scoped to just this one repo | Nowhere — doesn't exist |

My recommendation is the stored token, same as the code-push discussion — a fine-grained,
single-repo, contents-only token is a proportionate risk for a fantasy football repo, and it's the
only way this stays genuinely hands-off. Flag if you'd rather trade some automation for not
storing a credential at all.

---

## Phase 3 — Wire the deterministic analysis in (Gap 2)

Don't try to make `weekly.js`'s agents call Python mid-workflow — the Workflow tool's `agent()`
calls are LLM calls, not code execution, so that was never the right shape. Instead, move the
Python earlier:

**New Step 3 (runs before the Workflow, after Step 2.5's diff):** run
`analysis/opponent_pressure.py`, `waiver_contention.py`, and `keeper_equity.py` against the fresh
state file, producing one `analysis_output.json` — verified pressure scores, the Monte Carlo
waiver-landing probabilities, the keeper-equity board, and critically, the code-verified list of
who is and isn't a free agent.

**`weekly.js` changes:** pass `analysis_output.json` into the workflow as part of `args`. Every
agent prompt that currently says "verify availability yourself" or "estimate pressure" instead
gets handed the real numbers and is told to cite and reason from them, not re-derive them. This
turns the availability gate from an LLM instruction into what the plan always wanted: a
deterministic check the LLM can't route around.

**Why this order matters:** it also fixes a second-order issue for free — since `analysis_output.json`
gets computed from the *diffed* state (Step 2.5, Phase 2), the pressure scores are automatically
comparing this week to last week's real numbers instead of to nothing, which is the
`recent_scoring` gap the test agent flagged as still-open.

---

## Phase 4 — Prove the loop actually loops

Before trusting this on a real Tuesday:

1. Simulate two consecutive weekly runs by hand against the real repo clone — run week N, commit,
   then run week N+1 and confirm it reads week N's *pushed* state, not a stale bundle. Assert the
   diff, the `decisions_log` accumulation, and the waiver-order carry-over are all correct.
2. Confirm `analysis_output.json` actually changes the brief's wording — i.e., an agent given a
   verified "unrostered: true/false" flag doesn't independently re-litigate it.
3. Kill the run mid-workflow (simulate a usage cap) and confirm resuming doesn't double-commit or
   push a half-finished state.
4. First real Tuesday: explicitly check the push succeeded (`git log` shows the new commit) before
   trusting that the following week's diff will work. If the push silently failed, catch it there,
   not four weeks later when the whole history has a hole in it.

---

## Not in this plan (already known, not blocking)

- 2026 bye weeks — still need the real published schedule hand-entered once it exists; no code fix
  possible before then.
- ~104 rostered players still on stale Aug-2025 team/injury data outside your 12 — a refresh pass,
  not a loop-architecture problem. Worth scheduling once, separately.
- Waiver clock time, DEF scoring fix, keeper deadline — still open questions for the commissioner,
  tracked in `league_config.open_questions`, unaffected by any of the above.
- The dashboard / live website — explicitly parked.

---

## What I need from you to start

The repo (and token) from Phase 0. Once that's in hand: Phase 1 is quick, Phase 2 and 3 are the
real work, Phase 4 is what actually earns trust in the result before the season starts using it
for real.
