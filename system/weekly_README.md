# `weekly.js` — the Tuesday workflow engine

The muscle half of the Sunday Scaries system. It implements Parts 3, 4 and 6 of
`weekly_system_plan.md`: eighteen agents across three phases that turn last week's state file plus
fresh Sleeper data into a single Tuesday action card and the next state file.

It is a **Cowork Workflow script**, not a Node program. Do not run it with `node`. The workflow
runtime injects four globals — `phase()`, `agent()`, `parallel()` and `args` — and evaluates the file
body as an async function, which is why the script legally ends in a top-level `return`.

---

## What it does

```
Phase 1  Intelligence      15 sonnet agents, all fired at once
           9 x opponent model      one per rival, four-pressure scoring (Part 4)
           4 x news sweep          sliced by TOPIC, never by team
                                     injury + practice participation
                                     snap-count + target-share movers
                                     depth-chart + role changes from beat reporting
                                     breakout + buy-low (and the sell-high mirror)
           1 x free-agent board    ranked by ROS value in THIS format, availability-gated
           1 x my-team             lineup, byes, injuries, sell-high, drop candidates

Phase 2  Cross-Analysis    2 opus agents (effort: high), fired in parallel
           waiver contention model   who picks ahead of Andrew, and what actually reaches him
           trade board               Andrew's surplus x each rival's acute need, sendable offers

Phase 3  Synthesis         1 opus agent (effort: high)
           the 8-part Tuesday brief + the complete next state file as JSON
```

The news agents are sliced by **topic rather than by team** on purpose. Nine team-sliced agents all
read the same wire and return the same nine copies of the same injury report; four topic-sliced
agents each read a different wire. Same cost, four times the coverage.

---

## Running it

Invoke it with the Workflow tool, pointing at the absolute path:

```
Workflow: /home/claude/sunday_scaries/system/weekly.js
args:     week=7
```

From the `sunday-scaries` skill this is step 4 of 5. The full order of operations is:

1. **WebFetch** the URLs in `system/fetch_manifest.md` into `system/raw/`.
   Sleeper is unreachable from bash/python in this sandbox — WebFetch is the only path out.
2. **Run** `system/state_builder.py` to normalise `raw/` into `system/state/week_N.json`.
3. **Run** `system/analysis/build_analysis_output.py system/state/week_N.json` to produce
   `system/state/week_N_analysis_output.json` — see **"The analysis baseline"** below. This has to run
   as a separate step *before* the workflow, not from inside it: `agent()` calls are LLM calls, not code
   execution, so there is no way for a prompt mid-workflow to invoke Python. Moving the deterministic
   analysis modules earlier, into their own pre-workflow step, is the only shape that actually works.
4. **Run this workflow.**
5. **Write** the two things it returns to disk (see *Return shape* below). The workflow itself does
   no file I/O — it has no `fs`. Every agent reads its own inputs with the Read tool, and the caller
   writes the outputs.
6. **Run** `system/merge_state.py --week N` to fold the agent's `opponent_model`, `keeper_equity`,
   `decisions_log` and `open_questions` into the deterministic `week_N.json` from step 2.
   `state_json` goes to `week_N.synthesis.json`, **never** straight to `week_N.json` — that file
   holds facts computed from the Sleeper payloads and a model must not overwrite them.

Before running, make sure these exist:

| Directory | Why |
|---|---|
| `system/raw/` | the fetched Sleeper JSON every agent reads |
| `system/state/` | last week's state file, this week's analysis-output file, and where this week's state lands |
| `system/reports/` | where the markdown brief lands |

---

## The analysis baseline — Phase 3 of `weekly_loop_closure_plan.md`

**The gap this closes:** `weekly.js` cannot call `analysis/opponent_pressure.py`, `waiver_contention.py`
or `keeper_equity.py` itself — those are Python and the Workflow tool's `agent()` calls are LLM calls,
not code execution. Before this existed, the "availability gate" and the pressure/contention model ran
entirely as prompt instructions ("verify availability yourself", "estimate pressure"), which is exactly
what the plan's hard rule says must never happen: a fact that must be exactly right belongs in
deterministic code, not a model's self-discipline.

The fix is to run the Python **before the Workflow starts**, against the same state file, and hand the
result to every agent as a fourth input alongside the state file, the raw payloads and the reference
docs:

```
python3 system/analysis/build_analysis_output.py system/state/week_N.json
# -> writes system/state/week_N_analysis_output.json
```

That file has five top-level sections:

| Section | Built by | What it is |
|---|---|---|
| `opponent_pressure` | `opponent_pressure.compute_league_pressure()` | per-rival vacancy/performance/role/depth pressure, keyed by `roster_id` (string). `role` is always 0 here — it is an external input the baseline cannot see, see below. |
| `predicted_claims` | `opponent_pressure.predicted_claims_from_pressure()` | a first-pass predicted-claims list per rival, keyed by owner name, run against the real verified free-agent pool |
| `waiver_contention` | `waiver_contention.contention_report()` | a full Monte Carlo (`DEFAULT_TRIALS=4000`) landing-probability report over every verified free agent, using `predicted_claims` as each rival's wishlist |
| `keeper_equity` | `keeper_equity.build_keeper_board()` / `optimal_keeper_slate()` | the ranked 2026 keeper board and legal best-3 slate, off `league_config.json`'s real keeper-cost provenance |
| `verified_free_agents` | pass-through of `state['free_agents']` plus a valued pool | the code-verified availability gate — a player must appear here (or as a DEF) to be recommended anywhere downstream |

`weekly.js` reads this as a **path**, exactly like `STATE_PATH` and `PREV_STATE_PATH` — the workflow has
no `fs`, so it never parses the JSON itself; every agent that needs it reads it with the Read tool. The
arg is `analysis_output` (or its short form `analysis`); it defaults to
`system/state/week_<N>_analysis_output.json`, matching the default state path.

**The contract is "baseline vs refine," not "baseline vs ignore" and not "baseline vs recompute."**
Every prompt that touches pressure, predicted claims, waiver contention or free-agent availability is
told explicitly: cite the baseline number, then say what you are adjusting it to and why, using
qualitative signal the baseline cannot see (it runs before the news agents, so it has zero role_signals
and zero beat-reporting input) — never silently recompute the arithmetic from scratch, and never
contradict `verified_free_agents`.

**Concrete example** (from a real run against `week_0.json`): the baseline's `waiver_contention.claim_sheet`
already puts Michael Penix at `probability_reaches_andrew: 1.0` because nobody ahead of Andrew in the
priority order shows a predicted claim on a QB. If a news agent's beat-reporting sweep turns up a QB
injury on `DannyBC1`'s roster (first pick in the order) that the box-score-only baseline had no way to
know about, the opponent-model agent for `DannyBC1` is expected to say exactly that — "baseline vacancy
was 0.0 for QB, but \[source, dated\] reports \[starter\] is now out; raising vacancy and predicted claims
accordingly" — not to silently leave Penix at 100% or, worse, invent a new number with no baseline
reference at all.

---

## Arguments

`args` is a free-form string (an object with the same keys also works). Everything is optional.

| Arg | Example | Default |
|---|---|---|
| `week` | `week=7`, `--week 7`, or a bare `7` | derived from the calendar |
| `waivers` | `waivers=priority` / `waivers=faab` | `ambiguous` — produces **both** answers |
| `state` | `state=/path/week_7.json` | `system/state/week_<N>.json` (the *deterministic* file; the agent's output is written alongside it as `week_<N>.synthesis.json`) |
| `prevstate` | `prevstate=/path/week_6.json` | `system/state/week_<N-1>.json` (week 1 → `week_0.json`) |
| `analysis_output` (or `analysis`) | `analysis_output=/path/week_7_analysis_output.json` | `system/state/week_<N>_analysis_output.json` — must exist before the run, built by `build_analysis_output.py` (see **"The analysis baseline"** above) |
| `report` | `report=/path/week_7.md` | `system/reports/week_<N>.md` |

**Week fallback chain:** explicit `week=` → a bare 1–18 integer anywhere in `args` → derived from
today's date against a season anchor of Tue 8 Sep 2026 (the Tuesday before Week 1 kickoff), clamped
to 1–18. An out-of-range week like `week=99` is rejected and falls through to the calendar. Before
the season opens the derived answer is week 1.

**Season phase is derived from the week, not passed in** (Part 5 of the plan). Weeks 1–3 apply the
small-sample rules; 4–8 turn the trade board aggressive; 9–13 count down to the week-13 deadline;
14–17 flip to streaming and, if elimination looks likely, to keeper-equity accumulation. The phase
rules are injected into every agent prompt, so a Week 2 run and a Week 12 run genuinely answer the
same question differently.

**Week 1 reads `week_0.json`, and that matters.** `state_builder.py` emits a week-0 *preseason
baseline* — post-draft rosters, keeper costs, opening waiver order — with no matchups, transactions
or scoring history. Earlier this script treated week 1 as having no predecessor and threw that
baseline away, leaving the season's first run blind. It now reads it, and tells every agent
explicitly that week 0 is a baseline rather than a played week, so nobody goes hunting for last-week
points that do not exist.

**`waivers` is deliberately three-valued, but the default is no longer a coin flip.** The raw Sleeper
settings show `waiver_type = 1`, which is Sleeper's code for **reverse-standings priority** (`0` =
rolling, `2` = FAAB). The 100-unit `waiver_budget` field that originally raised the FAAB question is
an inert default Sleeper carries on every league regardless of waiver mode, so it is not evidence of
FAAB. That agrees with the commissioner's note, so the prompts now lead with priority logic as the
working answer.

It still hedges, because nothing has been confirmed against a live processed claim and the two modes
imply completely different strategies: left at `ambiguous`, the contention model returns a
priority-ordered claim sheet *and* a FAAB bid percentage for every target, and states which
assumption it used. Pass `waivers=priority` or `waivers=faab` to collapse it once a real claim has
processed and settled the question.

---

## Return shape

The workflow returns an object; the caller writes two fields to disk.

```
{
  meta:          { workflow, league_id, season, week, week_source, run_date,
                   season_phase, waiver_mode_arg, args_received },
  write_targets: { report, state, deterministic_state, merged_state,
                   merge_command, prev_state },   // absolute paths, already computed

  report_markdown: "...",        // -> write to write_targets.report
  state_json:      "{...}",      // -> write to write_targets.state, which is
                                 //    week_N.synthesis.json, NOT week_N.json.
                                 //    Then run write_targets.merge_command.
  state_parsed:    { ... },      // JSON.parse of the above, or null
  state_parse_error: null,       // non-null means the agent emitted invalid JSON

  synthesis, contention, trade_board, my_team, free_agents, news, opponents,
  counts: { opponents, news, intelligence_agents_dispatched, intelligence_agents_returned }
}
```

**Always check `state_parse_error` before writing the state file.** If it is non-null the synthesis
agent emitted malformed JSON; write `report_markdown` anyway (the brief is still good) and either
repair `state_json` by hand or re-run just the synthesis phase. Never write a broken state file —
next week's run reads it as ground truth.

**Check `counts` too.** `intelligence_agents_returned` below `intelligence_agents_dispatched` means
an agent died. The run still completes; the synthesis just had less to work with, and it is told to
say so rather than pad. If two or three opponent models are missing, re-run before acting.

---

## Resuming after a usage interruption

This is the failure mode the plan expects, and the one worth understanding properly.

**Just re-run the same command with the same `args`.** Completed agents replay from cache, so a
resumed run only pays for what did not finish. A run that died during Phase 2 costs roughly the two
opus agents on resume, not the fifteen sonnet agents again.

The cache key is the agent's `label` plus its prompt text, so resumability depends on both being
stable between runs:

- **Labels are deterministic** — `opponent:pdustin`, `news:snap-target-movers`, `free-agents`,
  `my-team`, `waiver-contention`, `trade-board`, `synthesis:week7`. No timestamps, no counters.
- **Prompts are stable within a calendar day.** The run date is embedded (the freshness gate needs
  it), so resuming *the same day* replays from cache. Resuming the next day changes every prompt and
  re-runs everything from scratch. If you get capped, resume before midnight UTC.
- **Pass the same `week` explicitly on resume.** If the first run derived its week from the calendar
  and you resume without `week=`, a date rollover silently changes the week and invalidates the whole
  cache. Read `meta.week` off the partial result and pass it back in.

Phase 1 downstream inputs are packed with a size cap (`pack()`, 25k–60k chars per block), so a single
verbose agent cannot blow the Phase 2 or Phase 3 context and force a restart.

If the run keeps dying in Phase 1, you can narrow it cheaply: run it once to warm the cache on the
agents that do succeed, then re-run. The nine opponent agents are the bulk of Phase 1 and they cache
independently of each other.

---

## Guardrails baked into the prompts

These are in the script rather than in the skill, so they survive being called from anywhere.

- **Availability gate.** This now runs in two layers. The code layer is `verified_free_agents` inside
  `analysis_output.json` (see above) — computed before the run, straight from every roster, and every
  agent is told it must not be contradicted. The prompt layer is the fallback: every agent that names a
  free agent NOT already in that baseline is told to verify him against all ten rosters itself before
  naming him. The FA agent still carries an `availability_verified` boolean per player and an
  `unverified_excluded` list for anything it adds beyond the baseline; the contention model is told to
  drop anything it cannot confirm either way. Recommending an already-rostered player is the most
  damaging failure this system has.
- **Freshness gate.** Every injury, snap, practice or role claim needs a named source with a date
  inside 7 days, and an `is_stale` flag when it is not. Wikipedia is banned for anything
  time-sensitive — a previous sweep had to be redone over exactly that.
- **Diff, don't snapshot.** Opponent agents are told their most valuable output is what *changed*
  since last week's `opponent_model` entry, not a fresh re-derivation of a settled roster.
- **Self-grading.** The synthesis agent fills in `outcome` on last week's `decisions_log` entries and
  appends this week's recommendations ungraded, so the system stays accountable to its own past calls.
- **Open questions travel.** FLEX 1 vs 2, waiver type, waiver processing time, and the DEF scoring
  fix are stated as unresolved in every prompt and must appear in section 8 of the brief.

---

## Verifying the script after an edit

`node --check` is required and is run, but be aware it is close to a no-op on this file: the
combination of an ESM `export` and a top-level `return` defeats Node 22's syntax auto-detection, and
it exits 0 even on a deliberately broken file. The real check is to parse the body the way the
workflow runtime does:

```bash
node --check /home/claude/sunday_scaries/system/weekly.js   # required, but weak

node -e '
const fs=require("fs");
const b=fs.readFileSync("/home/claude/sunday_scaries/system/weekly.js","utf8")
        .replace(/^export const meta =/,"const meta =");
new Function("args","phase","agent","parallel",
  "\"use strict\";return (async () => {"+b+"})()");
console.log("PARSE OK");'
```

That second form catches real syntax errors (verified against a deliberately broken copy — `node
--check` passed that same file).

**The strongest check is a full dry run with stubbed primitives**, which exercises arg parsing, phase
ordering, fan-out counts and the return shape for zero tokens. Save this as `/tmp/verify.mjs` and run
`node /tmp/verify.mjs`:

```javascript
import fs from 'node:fs'
const src = fs.readFileSync('/home/claude/sunday_scaries/system/weekly.js', 'utf8')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const fn = new AsyncFunction('args', 'phase', 'agent', 'parallel',
  src.replace(/export\s+const\s+meta\s*=/, 'const meta ='))

const seen = []
const agent = async (prompt, o) => {
  seen.push(o.label + ' [' + o.phase + '/' + o.model + ']')
  if (prompt.indexOf('undefined') !== -1) throw new Error('undefined leaked into ' + o.label)
  if (o.label.indexOf('synthesis') === 0)
    return { report_markdown: '# x', state_json: '{"meta":{}}' }
  return {}
}
const parallel = (thunks) => Promise.all(thunks.map(t => t()))
const out = await fn('--week 7', () => {}, agent, parallel)

console.log(seen.join('\n'))
console.log('agents=' + seen.length, 'week=' + out.meta.week, 'prev=' + out.write_targets.prev_state)
```

Expect **18 agents** — 15 sonnet in Intelligence, 2 opus in Cross-Analysis, 1 opus in Synthesis — and
a clean `write_targets`. Worth also re-running it with `args` set to `undefined`, `'7'`, `''` and
`{week: 12}` to confirm the fallback chain, and with some agents returning `null` to confirm a dead
agent degrades instead of crashing the run.

Two conventions the script sticks to, worth preserving on edit:

- **No template literals and no backticks anywhere**, prompts included. Variables go in by plain
  string concatenation.
- **`meta` is a pure literal** and the first statement in the file. The runtime reads it without
  executing the script.
