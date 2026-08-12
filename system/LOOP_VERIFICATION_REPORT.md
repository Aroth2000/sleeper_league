# Loop Verification Report — Phase 4 of `weekly_loop_closure_plan.md`

**Job:** adversarially verify that the weekly loop built by `loop:bootstrap`,
`loop:continuity-rewire` and `loop:analysis-wiring` actually loops — by executing it, not by
reading their self-reports and trusting them.

**Method:** everything below was run for real against a scratch copy of the real artifacts. No
step is reported as "should work" without a command and real output shown. Two real bugs were
found by execution and fixed directly (small, self-contained, in this run's lane); both fixes are
re-verified below, not just asserted. One thing could **not** be verified — a real `git push` to
GitHub — because there is still no `SUNDAY_SCARIES_GH_TOKEN`, and that is called out explicitly
rather than implied.

**Scratch environment used:** `/tmp/loop_verify_scratch/` (ephemeral — will not survive a
container reset; this report is the durable record of what was run and what it produced). The real
`/home/claude/sunday_scaries/repo_clone/` was never written to by this verification — confirmed at
the end of every destructive test (`git log`/`git status` on the real clone, unchanged throughout).

---

## 0. Setup

```
cp -r /home/claude/sunday_scaries/repo_clone /tmp/loop_verify_scratch/repo_clone
```

`git ls-remote https://github.com/Aroth2000/sleeper_league.git` returned nothing (empty output,
exit 0) — confirming, independently of `loop:bootstrap`'s claim, that the real public upstream
repo genuinely has zero commits right now. Every "pull" test below is therefore exercising the
**pull-against-a-still-empty-upstream** scenario, not a real "pull someone else's real commits"
scenario — that second scenario cannot be tested until a token exists and Phase 1's bootstrap
commit is actually pushed. This is stated explicitly here so it isn't confused with a full
round-trip test later.

---

## 1. "Week 1" simulation — pull, build, analyze, commit (no push)

### 1a. `repo_sync.py pull` against the scratch clone

```
$ python3 system/repo_sync.py pull --dir /tmp/loop_verify_scratch/repo_clone
repo_sync: existing clone found at /tmp/loop_verify_scratch/repo_clone, pulling...
WARNING: repo_sync pull: fast-forward pull failed (fatal: couldn't find remote ref main). ...
repo_sync: pull OK, clone is at /tmp/loop_verify_scratch/repo_clone
EXIT=0
```

This is the **existing-clone / empty-upstream** path (not a fresh clone) — correct exit 0, since
there is nothing upstream to be behind. See §4 for a bug found and fixed in this exact code path.

### 1b. Fake week-1 raw data (non-trivial, deliberately injected transaction)

Built `raw/{state_nfl,rosters,users,league,transactions_week1,matchups_week1}.json` in a scratch
raw dir, derived from the real `system/raw/*.json`, with one concrete roster change: **Andrew
(roster_id 2) drops Colby Parkinson (player_id 6865, bench TE) and adds Michael Penix (player_id
11559)**, who was a confirmed free agent in the real `week_0.json`. A matching
`transactions_week1.json` entry was added. Both player IDs were already present in the real
`players_cache.json`, so no cache-ingest step was needed for this test.

### 1c. `state_builder.py --week 1` against that raw data, with `week_0.json` already staged

```
$ python3 system/repo_sync.py get-state --week 0 --dir .../repo_clone --out .../state/week_0.json
repo_sync: copied .../repo_clone/data/week_00/state.json -> .../state/week_0.json   EXIT=0

$ python3 system/state_builder.py --week 1 --raw-dir .../raw --out-dir .../state --summary
...
-- TRANSACTIONS (week 1) ----------------------------------------
  [complete waiver    ] andrewroth32     +Michael Penix (QB-ATL)  -Colby Parkinson (TE-LAR) prio=4

-- DIFF vs PREVIOUS WEEK -------------------------------------------------
  vs week 0: 1 adds, 1 drops
  andrewroth32     +['Michael Penix (QB-ATL)'] -['Colby Parkinson (TE-LAR)']
EXIT=0
```

The injected transaction and the resulting `roster_diff` are both correct and exact. `state_builder.py`'s
own free-agent computation also reacted correctly without any special-casing: `week_1.json`'s
`free_agents.confirmed_available_known_players` lost "Michael Penix" and gained "Colby Parkinson"
versus `week_0.json` (checked by set-diffing the two files' name lists — `{'Michael Penix'}` removed,
`{'Colby Parkinson'}` added, 35 known players in both).

### 1d. `build_analysis_output.py` against the fake week-1 state

```
$ python3 system/analysis/build_analysis_output.py .../state/week_1.json --out .../week_1_analysis_output.json
wrote .../week_1_analysis_output.json (132,459 bytes)
EXIT=0
```

Verified the content actually reacted to the roster change, not just "ran without crashing":

| Check | week_0 baseline (real, pre-existing) | week_1 (this test's fake state) |
|---|---|---|
| Michael Penix in `verified_free_agents.valued_pool`? | **True** | **False** |
| Michael Penix `waiver_contention.claim_sheet` row | `probability_reaches_andrew: 1.0`, `order: 1` (present) | **absent** (he's rostered now, correctly dropped from the pool and the claim sheet) |
| Pool size | 55 | 55 (net zero — Penix swapped out, Parkinson swapped in) |

This is the exact worked example `weekly_README.md` cites (Michael Penix at probability 1.0 in the
baseline) — here shown flipping to "not in the pool at all" the moment Andrew's roster actually
contains him, which is the correct behavior for a code-verified availability gate.

### 1e. `merge_state.py` and `commit-and-push --week 1` (token unset)

Ran `merge_state.py` against the fake `week_1.json` / a stub `week_1.synthesis.json` — succeeded,
folded `open_questions` in, correctly ignored the stub's `meta` key and reported the empty
`opponent_model`/`keeper_equity`/`decisions_log` sections as skipped (exactly the "do not let a
model overwrite facts" contract).

```
$ SUNDAY_SCARIES_GH_TOKEN unset
$ python3 system/repo_sync.py commit-and-push --week 1 \
    --report .../reports/week_1.md --state .../state/week_1.json \
    --synthesis .../state/week_1.synthesis.json --dir .../repo_clone
repo_sync: staged ... -> data/week_01/report.md
repo_sync: staged ... -> data/week_01/state.json
repo_sync: staged ... -> data/week_01/state.synthesis.json
repo_sync: committed locally: week 1: Week 1 Tuesday Brief (SCRATCH TEST)
repo_sync: SUNDAY_SCARIES_GH_TOKEN is not set -- this is expected until a token exists. Skipping push. ...
EXIT=0
```

`git log` in the scratch clone: `56c44aa week 1: Week 1 Tuesday Brief (SCRATCH TEST)` on top of the
bootstrap commit. Confirmed committed, not pushed (correct — no token).

---

## 2. "Week 2" simulation — the actual continuity test, and a real bug found

**This is where an actual, concrete, execution-proven bug was found in the documented order of
operations, not a hypothetical.**

Built a second fake transaction for week 2: **Andrew drops Jordan Mason (RB, player_id 8408) and
adds Kaleb Johnson (RB, player_id 12504)**, a free agent from week 1's pool.

### 2a. Reproducing the bug: literal `SKILL.md` order, on a genuinely fresh container

`SKILL.md`'s Step 2 (before this report's fix) ran `state_builder.py` **before**
`repo_sync.py get-state`. `state_builder.py` has no `--prevstate` flag: it looks for last week's
state at a fixed path, `<out-dir>/week_{N-1}.json`, at the moment it runs. On a container that has
never seen week 1 locally (the actual "brand-new Tuesday session" scenario this whole system exists
to solve), that file does not exist yet unless something puts it there first.

```
$ python3 system/state_builder.py --week 2 --raw-dir .../raw_week2 \
    --out-dir .../state_fresh_container --dry-run
"no previous state at .../state_fresh_container/week_1.json; roster_diff will be empty (expected on the first run)"
```

**Confirmed: following the documented order exactly as written produced an empty diff on a fresh
container**, even though week 1's real state was sitting right there in the repo clone, one
`get-state` call away. This defeats the entire purpose of `repo_sync.py` — "no memory between
weeks" would have persisted in practice despite the repo existing.

### 2b. The fix, and re-verification that it actually fixes it

Fixed **`system/skill/SKILL.md` Step 2** directly: reordered the commands so
`repo_sync.py get-state --week {N-1}` runs **before** `state_builder.py --week {N}`, and added an
explanatory note (with a pointer back to this report) so nobody "fixes" the order back by accident
later. `players_cache.py ingest` still runs first, unchanged.

```
$ python3 system/repo_sync.py get-state --week 1 --dir .../repo_clone \
    --out .../state_fresh_container/week_1.json
repo_sync: copied .../repo_clone/data/week_01/state.json -> .../state_fresh_container/week_1.json   EXIT=0

$ python3 system/state_builder.py --week 2 --raw-dir .../raw_week2 \
    --out-dir .../state_fresh_container --summary
-- DIFF vs PREVIOUS WEEK -------------------------------------------------
  vs week 1: 1 adds, 1 drops
  andrewroth32     +['Kaleb Johnson (RB-PIT)'] -['Jordan Mason (RB-MIN)']
```

**Confirmed fixed**, with the corrected order, on the same fresh-container setup (no local
`week_1.json` before the `get-state` call): the exact injected week-2 transaction shows up
correctly in `roster_diff`, sourced entirely from the repo clone via the week-1 commit made in
§1e — this is the real continuity round trip working end to end.

### 2c. `build_analysis_output.py` for week 2, confirming content changes again

```
$ python3 system/analysis/build_analysis_output.py .../state_fresh_container/week_2.json \
    --out .../week_2_analysis_output.json
wrote .../week_2_analysis_output.json (132,471 bytes)   EXIT=0
```

| Check | week_1 (this test) | week_2 (this test) |
|---|---|---|
| "Kaleb Johnson" in `verified_free_agents.valued_pool` | True | **False** (Andrew now rosters him) |
| "Jordan Mason" in `verified_free_agents.valued_pool` | False | **True** (Andrew just dropped him) |
| Kaleb Johnson `waiver_contention.claim_sheet` row | present, `probability_reaches_andrew: 1.0`, `order: 22` | **absent** |
| Pool size | 55 | 55 (net zero, same swap pattern as week 1) |

Confirms `build_analysis_output.py` is not silently reusing stale input between weeks — its output
tracks the real roster delta both times it was exercised.

---

## 3. `weekly.js` prompt threading, week 1 vs week 2 (AsyncFunction harness, per `weekly_README.md`)

`node --check` was **not** relied on for this file — per this project's own documented finding, it
is close to a no-op on `weekly.js`. Used the harness `weekly_README.md` documents instead
(`AsyncFunction('args','phase','agent','parallel', src)`), run twice — once with `args='--week 1'`,
once with `args='--week 2'` — capturing every agent's real prompt string, not just whether the
script ran without throwing.

```
$ node /tmp/verify_loop_harness.mjs
=== WEEK 1 ===  agents=18  meta.week=1
  write_targets.prev_state=.../state/week_0.json
  meta.analysis_output_path=.../state/week_1_analysis_output.json
=== WEEK 2 ===  agents=18  meta.week=2
  write_targets.prev_state=.../state/week_1.json
  meta.analysis_output_path=.../state/week_2_analysis_output.json

=== DIFFERENCE CHECKS ===
OK   prev_state differs between week1 (week_0.json) and week2 (week_1.json)
OK   analysis_output_path differs and is week-specific (week_1 vs week_2)
OK   opponent prompts exist both weeks (9 each)
OK   all week1 opponent prompts cite week_1_analysis_output.json
OK   all week2 opponent prompts cite week_2_analysis_output.json
OK   no cross-week path leakage between the two runs
OK   week1 opponent prompts cite prev_state week_0.json
OK   week2 opponent prompts cite prev_state week_1.json
OK   free-agents (week1) cites week_1_analysis_output.json
OK   free-agents (week2) cites week_2_analysis_output.json
OK   waiver-contention (week1) cites week_1_analysis_output.json
OK   waiver-contention (week2) cites week_2_analysis_output.json
OK   trade-board (week1) cites week_1_analysis_output.json
OK   trade-board (week2) cites week_2_analysis_output.json
```

All 14 checks pass, 18/18 agents dispatched both runs, no `undefined` leaked into any prompt
(the harness throws on that and didn't).

**Important precision, not glossed over:** `weekly.js` has no `fs` — it threads the **path** to
`analysis_output.json` and `prevstate` into every prompt, correctly and week-specifically, as shown
above. It does **not** and cannot read the file's *contents* itself; that only happens at real
run time, when an actual agent uses the Read tool against that path. I did **not** run the real
Workflow with live LLM `agent()` calls (that costs real tokens across 18 agents, same call
`loop:analysis-wiring` made). So: proven — the path threading is correct and week-specific, and
separately (§1d, §2c) that the file *content* at that path genuinely changes week to week. Not
independently proven: that a live agent, at real run time, actually reads and correctly cites that
content. That gap is inherent to the design (verifying it would require a real paid run) and is the
same honest limitation `loop:analysis-wiring`'s own report already flagged — repeating it here
because it's the one link in this chain that remains unverified by execution.

---

## 4. Resume-safety

### 4a. Requested test: `commit-and-push --week 1` run twice in a row (simulated kill-and-resume)

Run 2, identical args, immediately after run 1 (§1e):

```
repo_sync: staged ... (same 3 files, same content)
repo_sync: nothing changed for week_01 (content identical to last commit) -- skipping commit, this run is idempotent.
repo_sync: SUNDAY_SCARIES_GH_TOKEN is not set ... EXIT=0
```

`git log` after: still exactly one `week 1:` commit. `git status --short` after: empty (clean tree).
**No double-commit, no corruption.** This is the literal scenario the task asked for.

### 4b. Extra: independently re-verified the token-set push path (not just trusting the prior
agent's self-report)

Set a fake token, ran `commit-and-push --week 1` a third time (identical content to run 1/2):

```
repo_sync: nothing changed for week_01 ... skipping commit
WARNING: repo_sync commit-and-push: push FAILED (auth or network). The commit is still safe locally...
  remote: access denied by the git proxy: Aroth2000/sleeper_league is not in this session's
  authorized repository set... fatal: ... 403
repo_sync: retry manually once the token/network issue is fixed with: ...
EXIT=1
```

This independently confirms (not just re-running the earlier agent's own test) that the push code
path genuinely executes a real `git push` with the token inlined in the URL, that it fails for a
believable, real reason (the sandbox proxy, not a bug in the script), and that the commit/idempotency
state was undisturbed by the failed push attempt. Checked directly afterward: `git remote -v` in the
clone shows the plain token-free URL, and `grep -c ghp_loopverify .git/config` returned `0` — the
fake token did not leak into any persisted git state.

### 4c. The real `repo_clone/` was never touched

`git log --oneline` / `git status --short` on `/home/claude/sunday_scaries/repo_clone/` (the real
one, not the scratch copy) checked immediately after every destructive test above — unchanged
throughout: still exactly the one `79524a4 Bootstrap repo...` commit, clean tree.

---

## 5. A second real bug found and fixed: `repo_sync.py pull`'s exit code did not match what `SKILL.md` told the caller to do with it

`SKILL.md` Step 0's table says: "Exit 0 → the clone ... is current" / "Exit non-zero → fall back to
the bundled snapshot." Reading `repo_sync.py`'s `cmd_pull` closely (not just running the happy
path): for an **existing** clone, if `git pull --ff-only` failed for *any* reason — empty upstream,
but also a genuinely diverged history, a mid-pull network drop, an auth change — the function
printed a `WARNING: ... may not be current` line and then **unconditionally returned 0 anyway**,
directly contradicting both its own warning and `SKILL.md`'s documented contract for that exit code.

Verified this concretely with a real diverged-history git setup (a bare repo, two independent
clones each committing something the other doesn't have, so `--ff-only` genuinely cannot succeed —
confirmed first with plain `git pull --ff-only`, which correctly exits 128 with "Not possible to
fast-forward"):

```
$ git pull --ff-only origin main
fatal: Not possible to fast-forward, aborting.        (plain git, EXIT=128 -- confirms the setup is real)

$ python3 system/repo_sync.py pull --dir .../diverge_test/clone     # BEFORE the fix
WARNING: repo_sync pull: fast-forward pull failed (...). Continuing with the existing local
clone, which may not be current.
EXIT=0                                                  <-- BUG: contradicts SKILL.md's own contract
```

**Fixed** in `system/repo_sync.py`: `cmd_pull` now distinguishes the one genuinely non-fatal case
(remote has no commits yet on this branch — git's exact message is "couldn't find remote ref
<branch>", which is this project's real, current, verified state) from every other ff-pull failure.
Only the former still returns 0; everything else now correctly returns 1.

Re-verified both branches after the fix:

```
# case 1: real empty-upstream scratch clone -- must still be 0
$ python3 system/repo_sync.py pull --dir /tmp/loop_verify_scratch/repo_clone
repo_sync pull: remote has no commits on 'main' yet (empty upstream -- expected until this repo
has been pushed to). The existing local clone has nothing to be behind; treating it as current.
EXIT=0

# case 2: the real diverged-history setup from above -- must now be 1
$ python3 system/repo_sync.py pull --dir .../diverge_test/clone
WARNING: repo_sync pull: fast-forward pull failed (fatal: Not possible to fast-forward, aborting.).
The existing local clone may NOT be current -- treating this as a failed sync.
EXIT=1
```

Both cases now behave exactly as `SKILL.md`'s Step 0 table already promised the caller. `SKILL.md`
itself needed no further change here — its documented contract was already correct; the
implementation was the thing that didn't match it.

---

## 6. `SKILL.md` end-to-end coherence re-check after edits

Ran `grep -n "^## Step"` after making the §2/§5 fixes: Step 0 → Step 1 → Step 2 → Step 3 → Step 4 →
Step 5, in order, no gaps, no duplicates. Specific cross-checks:

- **Step 3's pointer to the analysis baseline was previously a vague one-liner** ("Step 3 also now
  passes `build_analysis_output.py`'s output into the workflow — see `weekly_README.md`"), written
  by `loop:continuity-rewire` *before* `loop:analysis-wiring`'s work existed, exactly as that
  agent's own report flagged ("a one-line pointer... without asserting its implementation"). It was
  accurate as far as it went but incomplete in a way that mattered: **it never told the operator to
  actually run `build_analysis_output.py`.** Fixed directly: Step 3 now states the exact command,
  in the exact position (`state_builder.py` → `build_analysis_output.py` → the Workflow tool),
  matching `weekly_README.md`'s own documented run order and the default path
  `weekly.js` (`ANALYSIS_OUTPUT_PATH`, verified directly at `system/weekly.js` lines 177–178)
  actually looks for.
- Every other file `SKILL.md` points to as a result of the other two agents' work
  (`system/repo_sync.py`, `system/analysis/build_analysis_output.py`) exists on disk and behaves as
  described, per §1–§5 above.
- `system/reports/` and `system/skill/reference/*.md` (referenced by Step 4 and the "Reference
  files" table) both exist and are non-empty.
- `python3 -m py_compile` clean on every touched Python file
  (`repo_sync.py`, `state_builder.py`, `merge_state.py`, `analysis/build_analysis_output.py`).
- `python3 system/analysis/test_analysis.py` — all 76 tests still pass (unmodified modules).

---

## What passed (verified by execution, not self-report)

1. `repo_sync.py pull` against the real, still-empty public upstream: works, correct exit code
   (post-fix).
2. `repo_sync.py get-state` correctly extracts a given week's `state.json` out of a repo clone.
3. `state_builder.py`'s `roster_diff` correctly detects an injected roster change **when the prior
   week's state file has already been staged into its out-dir** — true for both the week-1-vs-0 and
   week-2-vs-1 transitions tested here, using two different injected transactions.
4. `build_analysis_output.py`'s output genuinely tracks real roster deltas between weeks — checked
   with concrete before/after diffs on `verified_free_agents.valued_pool` and
   `waiver_contention.claim_sheet`, twice.
5. `merge_state.py` correctly folds only the model sections, ignoring the rest.
6. `repo_sync.py commit-and-push` commits locally, correctly skips the push with
   `SUNDAY_SCARIES_GH_TOKEN` unset, and is genuinely idempotent on an identical re-run (no
   duplicate commit, clean tree) — the literal "kill mid-run and resume" scenario requested.
7. The push code path, when a token *is* present, genuinely attempts `git push` (proven by a real
   403 from the sandbox's git proxy, not a mocked failure) and never leaks the token into persisted
   git state.
8. `weekly.js` (via the documented `AsyncFunction` harness, `node --check` never trusted) threads
   week-specific `prevstate` and `analysis_output` paths into every relevant prompt correctly and
   distinctly across two different `week=` args, with 18/18 agents dispatched both times and no
   `undefined` leakage.
9. `SKILL.md` reads coherently end to end, Step 0 → Step 5, and its Step 3 pointer now accurately
   describes what `loop:analysis-wiring` actually built (a runnable command, not a vague reference).

## What was found broken and fixed directly in this run

1. **`SKILL.md` Step 2's documented order** (`state_builder.py` before `repo_sync.py get-state`)
   silently produced an empty `roster_diff` on a genuinely fresh container — the exact "no memory
   between weeks" failure the whole repo-sync system exists to prevent. **Fixed**: reordered to
   `get-state` before `state_builder.py`, with an inline explanation and a pointer back to this
   report (§2).
2. **`SKILL.md` Step 3's pointer to the analysis baseline** was accurate-but-incomplete (never told
   the operator to actually run `build_analysis_output.py`, or where in the sequence). **Fixed**:
   Step 3 now names the exact command and its position in the sequence (§6).
3. **`repo_sync.py pull`'s exit code did not match `SKILL.md`'s own documented contract** for it —
   it returned 0 even when a fast-forward pull genuinely failed for a reason other than "empty
   upstream," contradicting its own printed warning. **Fixed**: only the verified,
   currently-real "empty upstream, nothing to be behind" case still returns 0; every other pull
   failure now correctly returns 1, matching `SKILL.md` Step 0's table (§5).

## Known issues — NOT fixed here, flagged for a human/design call

1. **No push token exists.** Every `commit-and-push` run in this report, and in
   `loop:bootstrap`'s and `loop:continuity-rewire`'s own verification, is local-commit-only. **A
   real `git push` to `github.com/Aroth2000/sleeper_league.git` has never been executed by any
   agent in this run and was not executed here either.** Once Andrew provides a fine-grained PAT
   (repo: `Aroth2000/sleeper_league`, contents read/write):
   ```
   export SUNDAY_SCARIES_GH_TOKEN=<token>
   cd /home/claude/sunday_scaries/repo_clone
   python3 /home/claude/sunday_scaries/system/repo_sync.py commit-and-push --week 0 \
     --state data/week_00/state.json          # or re-derive from the real bootstrap commit
   # or, simplest for the very first push of the existing bootstrap commit:
   git push -u origin main
   ```
   This is genuinely untested end to end (repo currently has zero commits on GitHub) and should be
   treated as such until someone watches a real push land and confirms with
   `git log origin/main --oneline` after a fresh `git fetch`.
2. **The "baseline vs refine" contract between `analysis_output.json` and a live LLM agent** is
   verified only at the level of "the right path is threaded into the right prompt" (§3) and "the
   file's content is genuinely fresh" (§1d, §2c) — not at the level of "a real agent, given that
   path, actually reads it, cites it, and refines it correctly instead of ignoring or contradicting
   it." That requires a real paid 18-agent run and was out of scope for both this report and
   `loop:analysis-wiring`'s own verification, for the same reason (token cost).
3. **`state_builder.py` has no `--prevstate` override flag.** The fix in §2 works by relying on the
   fixed-path convention (`<out-dir>/week_{N-1}.json`), which is sufficient for the documented flow,
   but it means anyone scripting around `state_builder.py` directly (outside `SKILL.md`'s exact
   sequence) can silently reproduce the same bug found in §2a by getting the order wrong again. A
   more robust fix would be an explicit `--prevstate PATH` flag on `state_builder.py` itself so the
   dependency is impossible to get backwards; not built here since it touches a file
   (`state_builder.py`) this run's lane does not own and the documentation-level fix in §2 is
   sufficient to close the loop as specified in the plan.
4. **Week-directory naming is zero-padded 2-digit** (`week_00`..`week_99`), as
   `loop:continuity-rewire` already flagged — not a bug, just a ceiling worth knowing about; a
   normal 18-week season never approaches it.

---

## Files touched by this verification run

- `/home/claude/sunday_scaries/system/skill/SKILL.md` — Step 2 reordered (get-state before
  state_builder.py) and Step 3 completed (names the `build_analysis_output.py` command explicitly).
- `/home/claude/sunday_scaries/system/repo_sync.py` — `cmd_pull` exit-code fix (§5).
- `/home/claude/sunday_scaries/system/LOOP_VERIFICATION_REPORT.md` — this file.
- **Not touched:** `/home/claude/sunday_scaries/repo_clone/` (the real one — confirmed clean/
  unchanged throughout, §4c), `system/weekly.js`, `system/weekly_README.md`,
  `system/analysis/build_analysis_output.py`, `system/state_builder.py`, `system/merge_state.py`,
  any file under `system/state/` (real one — only `week_0.json` and `week_0_analysis_output.json`
  exist there, both pre-existing and untouched).

## How to reproduce

All commands above are real and copy-pasteable; the scratch dir was `/tmp/loop_verify_scratch/`
(ephemeral, not part of the repo). The harness used for §3 was written to
`/tmp/verify_loop_harness.mjs` (also ephemeral) — its full source, reproduced here since it will not
survive a container reset:

```javascript
import fs from 'node:fs'
const src = fs.readFileSync('/home/claude/sunday_scaries/system/weekly.js', 'utf8')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const fn = new AsyncFunction('args', 'phase', 'agent', 'parallel',
  src.replace(/export\s+const\s+meta\s*=/, 'const meta ='))

async function runWeek(weekArg) {
  const seen = []
  const prompts = {}
  const agent = async (prompt, o) => {
    seen.push(o.label + ' [' + o.phase + '/' + o.model + ']')
    prompts[o.label] = prompt
    if (prompt.indexOf('undefined') !== -1) throw new Error('undefined leaked into ' + o.label)
    if (o.label.indexOf('synthesis') === 0)
      return { report_markdown: '# x', state_json: '{"meta":{}}' }
    return {}
  }
  const parallel = (thunks) => Promise.all(thunks.map(t => t()))
  const out = await fn('--week ' + weekArg, () => {}, agent, parallel)
  return { out, seen, prompts }
}
// ... then compare runWeek(1) vs runWeek(2)'s out.write_targets / out.meta / prompts as in §3.
```
