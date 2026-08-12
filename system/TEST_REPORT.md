# Integration test report — Sunday Scaries weekly system

Run date: 2026-08-08. Adversarial verification of the four parallel builds.
Everything below was executed, not read. Where I say "confirmed", there is a command behind it.

**Verdict: the system runs end to end, but it shipped with three silent-wrong-answer bugs and one
structural seam that would have destroyed the deterministic state file every single week.
All four are now fixed and verified. Two real gaps remain open and are not fixable here.**

Three of the four self-reports were substantially honest. The exception is the skill package: its
"cold-start rehearsal" passed against a *stale snapshot* and reported 71 tests where the live suite
has 76 — the discrepancy was visible in its own output and was not chased.

---

## 1. Inventory vs. claims

Every file the four agents claimed to create exists. Nothing is missing.

| Claimed by | Files | Status |
|---|---|---|
| Data layer | 13 (config, manifest, builder, cache, raw/, state/) | all present |
| Workflow | `weekly.js`, `weekly_README.md` | present |
| Analysis | 5 modules under `analysis/` | present |
| Skill | `SKILL.md` + 7 reference files + `sunday-scaries.skill` | present |

Two empty directories exist and are unclaimed: `system/reports/` (correct — `weekly.js` writes
briefs there) and `system/ui/` (orphan from an earlier run; harmless, nothing references it).

The workflow agent's stated limitation *"`system/fetch_manifest.md` does not exist yet"* is
**stale** — the data-layer agent landed it. That reference is now satisfied.

---

## 2. `weekly.js`

`node --check weekly.js` exits 0. **That check is worthless and the workflow agent was right to say
so.** I reproduced its finding: appending `const x = = = 5` to a copy still gives exit 0, because the
ESM export defeats Node 22's syntax auto-detection. Anyone relying on `node --check` here is
relying on nothing.

I rebuilt the runtime harness (`/tmp/harness.mjs`) — `AsyncFunction('args','phase','agent','parallel', body)`
— and it correctly **rejects** the broken copy with `SyntaxError: Unexpected token '='`. Negative
control passes, so the method is valid. Against the real file:

- `meta` evaluates as a **pure literal** in isolation: `name: 'sunday-scaries-weekly'`,
  304-char description, `phases: ["Intelligence","Cross-Analysis","Synthesis"]`. No references
  to runtime state.
- **18 agents dispatched**, all carrying a schema: Intelligence 15 (all `sonnet`) —
  9 `opponent:*`, 4 `news:*` matching the four required topic slices, `free-agents`, `my-team`;
  Cross-Analysis 2 (`opus`); Synthesis 1 (`opus`).
- `phase()` call order matches `meta.phases`. `parallel()` receives thunks, not promises.
- Zero `undefined` / `[object Object]` leaks into any prompt.
- **It does not call the Workflow tool internally.** `grep` for `Workflow`, `require(`, `import `,
  `fs.`, `readFileSync`, `writeFileSync` returns **nothing**. It is pure orchestration with no I/O,
  exactly as documented.
- The `javascript` block in `weekly_README.md` executes verbatim and prints 18 agents.

---

## 3. Python

`py_compile` clean on all seven modules. `analysis/test_analysis.py` → **76 tests, OK** (the skill's
"71 tests" was measuring its own stale bundle — see §5).

`state_builder.py` executed against the real `raw/` from a foreign cwd. Output is **real data, not a
stub**: 222/222 players resolved, all 10 rosters mapped onto named starter slots, Andrew's lineup
rendered with real names (Kelce, Nacua, Nix, Jeanty), 5 real injuries surfaced, waiver order
computed with Andrew at #4 and the three teams ahead named, 35 confirmed-available free agents +
20 DEF, `week_0.json` at 58,896 bytes.

I then built a **synthetic Week 7** (real rosters + records + a real-shape `/matchups` payload +
transactions carrying `settings.priority` + an injured Andrew RB and an injured rival WR) and ran
the whole chain. Season phase correctly flipped to `trade_window`; transactions parsed with
`prio=3`; both injuries surfaced with `STARTER` flags; matchups normalised. A Week 8 run against
Week 7 produced a correct diff including `promoted_to_starter`.

Degradation: empty `raw/`, truncated JSON, zero-byte file → valid JSON emitted, `meta.degraded=true`,
corruption recorded in `meta.sources.unparseable`, no traceback. Missing `raw/` dir → exit 2.

---

## 4. `league_config.json` vs `league_reference.md` — checked field by field

Parses. **Every load-bearing constant matches**, verified three ways (reference doc ↔ config ↔ the
raw `league.json` payload):

- **Scoring** — programmatic comparison of 21 values across all three sources: `rec 0.5`,
  `rec_fd 0.5`, `rush_fd 0.5`, `pass_yd 0.04`, `rush/rec_yd 0.1`, `pass_td 4`, `rush/rec_td 6`,
  `pass_int -1`, `fum_lost -2`, DEF `sack 1 / int 2 / fum_rec 2`, points-allowed ladder
  `10/7/4/1/0/-1/-4`. **0 mismatches.**
- **Roster slots** — `QB,RB,RB,WR,WR,TE,FLEX,FLEX,SUPER_FLEX,DEF` + 6 BN. Byte-identical to
  `roster_positions` in the raw payload and to §2 of the reference doc.
- **roster_id map** — all 10 `roster_id → user_id → display_name` triples match `raw/rosters.json`
  joined to `raw/users.json`, and all 10 user_ids match §5 of the reference doc. Andrew =
  roster_id 2, user_id 1128203360286429184, waiver_position 4. Correct.
- **Andrew keeper costs** — all 12 rows match §6 exactly: Nacua R2, Walker R4, Evans R4,
  McMillan R5, DeVonta R6, Kelce R7, Mixon R8, Mason R10, Nix R12, Javonte R13, Jameson R14,
  Jeanty R1-ineligible. Pick map matches §8 including all three forfeited picks (33/113/133) and
  all three 19-pick dead zones.
- **Waiver type** — I re-derived this independently rather than trusting either agent:
  `raw/transactions_2025_week8.json` has **33 transactions, 3 carrying `settings.priority`, 0 with a
  non-empty `waiver_budget`.** That is direct empirical evidence for rolling priority. The
  `waiver_budget: 100` field is present but demonstrably unused. **Priority, not FAAB — confirmed.**

**One genuine contradiction found and fixed** — see Fix 4 below.

`flex_count` is marked `resolved_by_api` in the config (Sleeper enforces 2 FLEX) so the builder
suppresses it from `open_questions`, while `weekly.js` still surfaces it in the brief's open-questions
section. That divergence is deliberate and documented on both sides, not a bug.

---

## 5. The `.skill` archive — **was shipping a known-broken module**

`sunday-scaries.skill` exists, `zipfile.testzip()` returns `None`, `SKILL.md` sits at
`sunday-scaries/SKILL.md` with valid YAML frontmatter (`name: sunday-scaries`, 697-char
description), all 7 reference files present, `quick_validate.py` → "Skill is valid!".

**But the bundle was stale, and that was not cosmetic.** I diffed every bundled file against live:
`weekly.js`, `state_builder.py`, `players_cache.py`, `league_config.json`, `players_cache.json` and
`scoring.py` were identical — but all four other analysis files differed, and the bundled test suite
ran **71 tests, not 76**.

The archive contained the version of `keeper_equity.py` from *before* the "drop Travis Kelce" fix.
Proof, running the same input through both:

```
input: {"player":"Travis Kelce","position":"TE","keeper_cost_round":7}

BUNDLED (shipped)  market_round 17, surplus_rounds -5, note "surplus is a lower bound"
LIVE               market_round null, surplus_rounds null, valued false,
                   "NO PROJECTION SUPPLIED -- surplus is unknown, not zero and not
                    negative. Do not rank or drop on this row."
```

The `.skill` is the disaster-recovery payload and the file Andrew actually receives. Restoring from
it would have reinstated a keeper board that confidently recommends dropping elite unprojected
players. **Rebuilt — see Fix 5.**

---

## 6. Week 7 trace — where the seams are

Scenario: Week 7, Andrew's starting RB (Javonte Williams) is Out, rival DannyBC1's starting WR
(Amon-Ra St. Brown) is Out. Traced through real execution, not on paper.

| Step | Owner | Result |
|---|---|---|
| Fetch 8 endpoints → `raw/` | WebFetch + `fetch_manifest.md` | filenames in manifest, `SKILL.md` and `state_builder.py` **agree exactly**, incl. the `transactions_week{N}.json` fallbacks |
| Ingest identities | `players_cache.py ingest` | **BUG — Fix 1** |
| Build state | `state_builder.py --week 7` | works; **matchup BUG — Fix 2** |
| Score pressure | `analysis/opponent_pressure.py` | Andrew RB 0.66, DannyBC1 WR 0.63, evidence strings name both injured players. Correct. **But nothing calls it — Seam A** |
| Contention | `analysis/waiver_contention.py` | works standalone. **Nothing calls it — Seam A** |
| 18 agents | `weekly.js` | orchestration verified |
| Write state | caller | **STRUCTURAL — Fix 3** |

### Seam A — `weekly.js` and `analysis/*.py` do not know each other exist

`grep` across `weekly.js` for `analysis`, `opponent_pressure`, `waiver_contention`, `keeper_equity`,
`scoring.py`: **zero matches.** Four tested modules and 76 tests that no agent is ever told to run.
Every number they produce deterministically is instead re-derived in prose by an LLM.

The concrete cost: Part 7 of the plan says the availability gate *"belongs in deterministic code, not
in a prompt."* `waiver_contention.py` implements it in code. `weekly.js` implements it as an
`availability_verified` boolean in a prompt schema. The gate the plan demanded is not the gate that
runs. **Not fixed** — wiring Python execution into the agent prompts is a design change, not a bug
fix, and it is the top item for whoever picks this up next.

### Seam B — performance and depth pressure had no data source at all

`recent_scoring` and `role_signals` are consumed only inside `opponent_pressure.py`. Nothing
anywhere produced them. So of the plan's four Part-4 pressures, **only VACANCY ever fired**; the
module was a vacancy detector wearing a four-pressure label. Partially fixed — see Fix 6.

### Seam C — shape mismatch between the two state schemas (crashes)

`opponent_pressure.py` reads `team["starters"]` as a list of **dicts** (`{player_id, pos, ...}`),
which is what `state_builder.py` emits. The synthesis agent is told to emit the plan's Part-2
schema, where `starters` is a list of **bare id strings**. Fed the plan-shaped version:

```
CRASH: AttributeError 'str' object has no attribute 'get'
```

This was reachable because of Fix 3 below. With Fix 3 applied the deterministic shape survives and
`opponent_pressure` parses the merged file cleanly (verified: 10 teams scored).

---

## Fixes applied

### Fix 1 — `players_cache.py`: injury updates were silently discarded  ★ highest severity

`ingest_records` routed a `/v1/players/nfl/{id}` response to the authoritative
`ingest_player_object` **only if** the record happened to contain `fantasy_positions`,
`search_rank` or `birth_date`. Any record missing all three fell through to `ingest_draft_pick`,
which carries no injury fields and is not authoritative.

Why that matters: the manifest itself documents that "WebFetch transcribes JSON through a small
model, so it is not guaranteed lossless" — and the three keys chosen as the discriminator are
exactly the decorative ones a summarising model drops first. Proven with a realistic payload:

```
in : {player_id 7588, first_name Javonte, last_name Williams, position RB,
      team DAL, injury_status "Out", injury_body_part "Knee"}
out: {... no injury_status, no injury_body_part}      # silently, no error
```

An injured player reads as healthy → vacancy pressure reads 0 → the opponent model misses the
single highest-signal input it has. And because the misrouted record is non-authoritative, a
*healed* player would keep a stale `Questionable` forever — the exact bug the data agent believed
it had fixed.

**Changed:** added `PLAYER_OBJECT_KEYS`, a 15-key set (injury/status/depth/bio fields) — any one
surviving key routes correctly. **Verified:** `injury_status` now lands; the authoritative-null
heal-clear still works; rebuilt the whole cache from scratch and diffed against the pre-fix cache —
**222 ids, 0 field differences, no regression**.

> Also found: `players_cache.py` has **no `--cache` flag**. `--dir` is cwd-relative but the cache
> path is script-relative, so running an ingest against a test fixture silently writes into the
> production cache. I did this to myself during testing and restored from the bundle. Not fixed
> (new flag = new surface), but do not run an ingest against fixtures without copying the script.

### Fix 2 — `state_builder.py`: empty starter slots shifted every subsequent player's score

`starters_points` is index-aligned to the **unfiltered** `starters` array. The code filtered `"0"`
placeholders out of `starters` first, then indexed `starters_points` by the *filtered* position, so
every starter after an empty slot received the previous player's points.

**This fires on live data today.** `raw/rosters.json` shows jomud (roster 4) currently carrying a
`"0"` in his starters array. Against my Week 7 fixture: 5 misaligned starters on that roster —
Juwan Johnson credited 7.94 when he actually scored 11.38, and so on down the slot list.
Performance pressure is computed from these numbers.

**Changed:** zip `starters` with `starters_points` **before** filtering; used `is not None` so a
genuine 0.0 is not treated as missing. **Verified:** 99 starters across 10 rosters, **0 alignment
errors** (was 5).

This was the code path the workflow agent flagged as "never run against a real payload." It was
broken.

### Fix 3 — the state file was being destroyed every week  ★ structural

`SKILL.md` Step 2 ran `state_builder.py --week N`, writing `state/week_N.json`. Step 4 then wrote
the synthesis agent's `state_json` to `write_targets.state` — **the same path**. The deterministic,
API-derived state file was overwritten by an LLM's reconstruction of it, every run. Next week's
`prev_state` then read the reconstruction as ground truth, so drift compounds. And the synthesis
prompt explicitly instructed the model to rebuild `standings`, `teams` and `transaction_log` by
hand from raw payloads — work `state_builder.py` had just done deterministically, which is exactly
what Part 3 Phase 0 and Part 7 of the plan forbid. Seam C then crashes on the result.

**Changed:**
- `weekly.js`: added `SYNTH_STATE_PATH` (`week_N.synthesis.json`); `write_targets.state` now points
  there, plus new `deterministic_state`, `merged_state` and `merge_command` fields.
- `weekly.js` synthesis prompt: now emits **only** `opponent_model`, `keeper_equity`,
  `decisions_log`, `open_questions`, and is told the mechanical sections already exist.
- `weekly.js` shared context: `STATE_PATH` reframed from *"may not exist yet"* to *"ALREADY BUILT
  — read it, it is ground truth"*, so 18 agents stop re-deriving facts.
- **New `system/merge_state.py`** — deterministic merge: model sections from the synthesis file,
  everything else from the builder, `open_questions` unioned, `.prebuild.json` backup, atomic
  replace, and it **refuses to touch the deterministic file** if the synthesis JSON is missing or
  malformed.
- `SKILL.md` Step 4 and `weekly_README.md` updated to the 5-step order.

**Verified:** fed the merger a synthesis payload containing deliberately poisoned facts
(`standings[0].wins = 99`, `meta.league_id = "BOGUS"`, `teams["2"].starters` as bare strings) —
real values preserved, poison ignored and reported, model sections taken,
`open_questions` unioned 6→7, `opponent_pressure.py` parses the merged file. Missing synthesis
file → deterministic file untouched, exit 1. `weekly.js` re-verified: still 18 agents, 15/3 model
split, correct `write_targets`.

### Fix 4 — `league_config.json` contradicted itself on the waiver clock

The same `waivers` object asserted (a) `waiver_day_of_week: 2` with `0=Sunday..6=Saturday`, i.e.
Tuesday; (b) `waiver_day_name: "Wednesday"`; (c) "claims process at approximately 00:00 US
Eastern"; (d) "the Tuesday run must land EARLY Tuesday"; and (e)
`run_deadline_guidance: "Submit claims before Tuesday 18:00 ET"`. (c)+(d) and (e) are mutually
exclusive. If processing really is Tuesday 00:00 ET, **the entire Tuesday-run premise is already
too late.**

I did not guess a value. **Changed:** rewrote `_day_note` to state both readings and that they give
opposite answers, added `waiver_day_name_verified: false`, and changed `run_deadline_guidance` to
the only advice safe under both readings — **submit by Monday night ET**. **Verified:** config still
parses, `state_builder` and `keeper_equity` still load it, 76 tests still pass.

### Fix 5 — rebuilt `sunday-scaries.skill`

Repacked from current files, now including `merge_state.py` (31 files, 180 KB). **Verified:**
`testzip()` → `None`; `quick_validate.py` → "Skill is valid!"; exactly one `SKILL.md`; full
cold-start rehearsal from a clean unzip — **76 tests OK**, `state_builder.py` prints correct
standings, `players_cache.py` reports 222/222, `weekly.js` parses and dispatches 18 agents; every
bundled file byte-identical to live.

### Fix 6 — gave `recent_scoring` a producer

Added `recent_scoring_from_states(state_dir, week, window=3)` to `opponent_pressure.py` plus a
`--with-recent-scoring` CLI flag. It assembles `{player_id: {week: points}}` from the last N weekly
state files' `matchups.by_roster`, skipping missing weeks rather than faking them.

**Verified:** built 167 players' scoring from the Week 7 fixture and re-scored the league;
performance and depth now measurably move the numbers (DannyBC1 WR 0.63 → 0.23 once real bench
viability is measured instead of assumed). 76 tests still pass; default CLI unchanged.

> Calibration warning that follows from this: the module renormalises weights over components that
> *have* data, so **pressure scores computed without `recent_scoring` are not comparable to scores
> computed with it.** Do not compare a Week 3 number to a Week 8 number across that boundary.

### Fix 7 — doc drift

`SKILL.md` and `reference/data_layer.md` said "71 tests"; the suite has 76. Corrected, and
`merge_state.py` added to the `SKILL.md` file map.

---

## Still broken / still open — do not let these get lost

1. **`weekly.js` never invokes `analysis/*.py`** (Seam A). Four tested modules, 76 tests, zero
   callers. Most importantly, the Part-7 availability gate runs as a prompt boolean rather than the
   deterministic check the plan requires. **This is the top remaining item.**
2. **2026 NFL bye weeks are empty.** `bye_coverage` returns `status: "unknown"` for all 10 teams and
   `bye_player_ids` never fires. Blocks real bye analysis from ~Week 4. Correctly refuses to guess.
3. **103 rostered players carry Aug-2025 draft-vintage team and injury data.** This is how Mike
   Evans read as TB after signing with SF. Surfaced in `meta.sources.players_cache.stale_rostered`.
   Fix 1 makes the refresh actually stick — it would not have before.
4. **Waiver processing clock time unconfirmed** (Fix 4). Until confirmed, submit Monday night.
5. **DEF scoring fix unconfirmed** — `yds_allow` tiers are still present in the 2026 config, so a
   DEF can bank 15 points before making a play. All DEF totals and DEF pressure are provisional.
6. **No agent has run against the live model.** Orchestration is verified; prompt quality and schema
   conformance in practice are not.
7. **`free_agents` is a proof of non-availability, not a complete pool** — correct and clearly
   labelled in the state file, but a player absent from the 222-id cache is *unknown*, not available.
8. **`players_cache.py` has no `--cache` flag**, so there is no safe way to test an ingest.

## Command log for re-verification

```bash
cd /home/claude/sunday_scaries/system
python3 -m py_compile state_builder.py players_cache.py merge_state.py analysis/*.py
cd analysis && python3 test_analysis.py            # 76 tests, OK
cd .. && python3 players_cache.py stats            # 222 / 222 / 0 unresolved
python3 state_builder.py --dry-run --summary
node /tmp/harness.mjs weekly.js week=7             # NOT node --check: that is a false pass
python3 merge_state.py --week 0 --dry-run
python3 /mnt/skills/examples/skill-creator/scripts/quick_validate.py <unzipped skill>
```
