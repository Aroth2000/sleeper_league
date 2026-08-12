---
name: sunday-scaries
description: Runs Andrew's Sunday Scaries fantasy football system (Sleeper, 10-team superflex half-PPR-plus-first-down keeper league) end to end from any chat, with no prior history. Use for the Tuesday update, the weekly fantasy brief, or any in-season question about this league - waiver claims and pickups, who to start or sit, lineup help, drop candidates, trade offers, opponent scouting, keeper decisions and keeper equity, or rebuilding state after a container reset. Triggers on - tuesday update, fantasy update, sunday scaries, weekly fantasy brief, waiver recommendations, what should I claim, who should I start, start/sit, lineup help, fantasy trade offers, keeper board, league intel.
---

# Sunday Scaries — the Tuesday system

One command, fired any Tuesday, that produces the week's action plan: lineup, ordered waiver
claims, drop candidates, trade offers, and an intel brief on what all nine rivals are about to do.

**The files are canonical, not the chat.** Everything needed to run is on disk. Read state from
files, never from memory of a previous conversation.

```
ROOT = /home/claude/sunday_scaries
  system/league_config.json     league constants (hand-verified against the API)
  system/players_cache.json     player_id -> name/pos/team/injury, built incrementally
  system/fetch_manifest.md      the WebFetch <-> builder contract, full detail
  system/players_cache.py       ingest / lookup / unresolved / stale / stats
  system/state_builder.py       raw/*.json  ->  state/week_N.json
  system/repo_sync.py           the loop's durable memory: pull/push data/week_NN/ against
                                the git repo, since a Tuesday session has no memory of its own
  system/merge_state.py         folds the agent's opponent_model/keeper_equity/decisions_log/
                                open_questions into week_N.json without overwriting facts
  system/weekly.js              the 18-agent workflow (Workflow tool, NOT node)
  system/analysis/*.py          scoring, opponent_pressure, waiver_contention, keeper_equity
                                (+ test_analysis.py — 76 tests, run it after any edit)
  system/raw/                   fetched Sleeper JSON lands here
  system/state/week_N.json      the local working copy. week_0.json is the preseason baseline.
  system/reports/week_N.md      the delivered brief
  repo_clone/                   working directory for the git-backed archive (see Step 0), default
                                path repo_sync.py uses -- data/week_NN/{report.md,state.json,
                                state.synthesis.json} for every week that has closed
```

## Two hard environment facts

1. **Nothing in this sandbox can reach `api.sleeper.app` except the WebFetch tool.** The proxy
   returns 403 on CONNECT. Never write or run Python/curl that calls Sleeper — it will fail.
   WebFetch writes raw JSON to disk; Python parses it. That split is not negotiable.
2. **`/players/nfl` (~5MB) will not come through WebFetch.** Never attempt it. The player cache is
   built incrementally from draft-pick payloads and per-player calls. See `reference/data_layer.md`.

## Step 0 — sync the repo, then orient

**Every Tuesday firing is a brand-new session with no memory of last week's session.** The only
durable memory this system has is the git repo (`github.com/Aroth2000/sleeper_league`), so the
first thing every run does — before reading anything else — is try to sync it:

```bash
python3 /home/claude/sunday_scaries/system/repo_sync.py pull
echo $?
```

Branch on the result immediately, out loud, in whatever you say back to Andrew:

| Result | Do this |
|---|---|
| Exit 0 | The clone at `repo_clone/` (default; override with `--dir`) is current. This is the source of truth for "last week's real state" in Step 2. |
| Exit non-zero | **Fall back to the skill's bundled snapshot exactly as documented before this repo existed** — `system/state/week_N.json` on local disk is what you have. **Say so plainly in the delivered brief** — e.g. "repo sync failed this run, working from the last locally-bundled state, continuity may be stale." Never fail silently; this is the same non-negotiable guardrail as the availability and freshness gates below. |

Then orient:

```bash
ls /home/claude/sunday_scaries/system/state/          # what weeks exist locally?
python3 /home/claude/sunday_scaries/system/repo_sync.py latest-week   # what weeks exist in the repo?
python3 /home/claude/sunday_scaries/system/state_builder.py --dry-run --summary
```

That summary prints the current week, waiver order, Andrew's lineup and which raw files are
missing — it is the fastest read on where the system stands. Then branch:

| What you find | Do this |
|---|---|
| `system/` missing entirely | **Cold start.** See "Rebuilding from nothing" below. |
| `repo_sync.py latest-week` prints `none` | Fresh start — no prior week anywhere in the repo. Proceed with no diff in Step 2 and say so; this is correct and expected for a brand-new league-year or a repo that was just bootstrapped. |
| State files exist, newest is last week | Normal run. Go to Step 1. |
| Newest state is this week, generated today | Already ran. Show the existing `reports/week_N.md` unless asked to re-run. |
| State exists but `meta.degraded == true` | A fetch was missing. Check `meta.sources.missing`, re-fetch those, rebuild. |
| Only `week_0.json` (or repo's `week_00`) and it is week 1 | Correct and expected. Week 0 is the preseason baseline, not a played week. |

Confirm the week from `raw/state_nfl.json` (fetch it fresh — step 1 below). Never assume the week
from the calendar if a real answer is available.

## Step 1 — fetch (WebFetch only)

Work through the ordered table in `system/fetch_manifest.md`. The core five, every week:

| # | URL | Save to `system/raw/` |
|---|---|---|
| 1 | `https://api.sleeper.app/v1/state/nfl` | `state_nfl.json` ← run first, it defines `{N}` |
| 2 | `https://api.sleeper.app/v1/league/1389753893356838912` | `league.json` |
| 3 | `.../league/1389753893356838912/rosters` | `rosters.json` |
| 4 | `.../league/1389753893356838912/users` | `users.json` |
| 5 | `.../league/1389753893356838912/transactions/{N}` | `transactions_week{N}.json` |
| 6 | `.../league/1389753893356838912/matchups/{N}` | `matchups_week{N}.json` |
| 7 | `.../players/nfl/{player_id}` (injured / new / unresolved ids) | append to `players_resolved.jsonl` |
| 8 | `.../players/nfl/trending/add?lookback_hours=24&limit=25` | `trending_add.json` |

Use this extraction prompt **verbatim** on every WebFetch call, or the summarising model will turn
the JSON into prose:

> Output ONLY a single line of raw JSON, no markdown fences, no commentary, no truncation. Copy
> every field value verbatim from the source. Use null for missing values.

Strip any ```json fences before writing. A 404 on a URL you know is good is a 15-minute cache
artifact — retry with a throwaway query string (`?r=1`). Filenames matter: a wrong name produces a
silently empty section, not an error.

## Step 2 — pull the real diff target out of the repo, THEN build state

**Order matters here and is not cosmetic.** `state_builder.py` has no `--prevstate` flag — it
silently looks for last week's state at the fixed path `system/state/week_{N-1}.json` (i.e.
`<out-dir>/week_{N-1}.json`) at the moment it runs, and if that file is not there yet it just
degrades to `roster_diff: {"status": "no_previous_state", ...}` with a warning, not an error. On a
genuinely fresh container that has never seen week `N-1` locally, the only place that file can come
from is the repo clone — so `repo_sync.py get-state` **must run before** `state_builder.py`, not
after. (An earlier version of this doc had these two steps in the opposite order; that silently
produced an empty diff on every first-run-in-a-fresh-container, which defeats the entire point of
Step 0's repo sync. Verified by execution in `system/LOOP_VERIFICATION_REPORT.md` §2 — running the
old order against a container with no local `week_{N-1}.json` reproduces the empty diff, and
swapping the order fixes it with no other change.)

```bash
cd /home/claude/sunday_scaries/system
python3 players_cache.py ingest --dir raw          # identities FIRST
python3 repo_sync.py get-state --week {N-1}         # THEN the diff target, before building state
python3 state_builder.py --week {N} --summary        # now state_builder finds week_{N-1}.json already staged
```

This copies `data/week_{N-1}/state.json` out of the `repo_sync.py pull` clone from Step 0 to
`system/state/week_{N-1}.json` — exactly where `state_builder.py`'s diff lookup and `weekly.js`'s
`prevstate` argument already look by default (see `weekly_README.md`), so nothing downstream has to
change to pick it up. **Backward compatibility, unchanged from before this existed:** if Step 0
reported the repo unreachable, or `repo_sync.py latest-week` said `none`, or `get-state` exits
non-zero because that week isn't in the repo yet, there is no prior week to diff against — proceed
with no diff, exactly as today, and say so in the brief rather than inventing a comparison.

Then check the cache is clean:

```bash
python3 players_cache.py unresolved --roster-file raw/rosters.json   # want: none
python3 players_cache.py stale      --roster-file raw/rosters.json   # want: short
```

Anything unresolved goes back to step 1 line 7. `stale` means the entry was seeded from the 2025
draft, so its **team and injury fields are 2025-vintage and must not be trusted** — Mike Evans is
cached from that draft as TB when he is on SF. Refresh stale entries for Andrew's roster and for
anyone you are about to recommend.

## Step 3 — build the analysis baseline, then run the workflow

**First, run the deterministic analysis stack** — `weekly.js` cannot call this Python itself
(`agent()` calls are LLM calls, not code execution), so it has to run as its own command, after
`state_builder.py` and before the Workflow tool:

```bash
python3 /home/claude/sunday_scaries/system/analysis/build_analysis_output.py \
  /home/claude/sunday_scaries/system/state/week_{N}.json
```

This writes `system/state/week_{N}_analysis_output.json` — opponent pressure, predicted waiver
claims, a full Monte Carlo contention report, the keeper board, and the code-verified free-agent
pool, all computed from box scores and rosters alone with zero qualitative input. `weekly.js`'s
`analysis_output` arg defaults to exactly this path, so no arg is needed if you ran this first. Full
detail, including the "baseline vs refine" contract every prompt is held to, is in
`weekly_README.md`'s "The analysis baseline" section.

**Then invoke the Workflow tool**, absolute path. It is not a node program; do not `node` it.

```
Workflow: /home/claude/sunday_scaries/system/weekly.js
args:     week={N}
```

18 agents: 15 sonnet in parallel (9 opponent models, 4 topic-sliced news sweeps, free-agent board,
my-team read), then 2 opus (waiver contention, trade board), then 1 opus synthesis.
Optional args: `waivers=priority|faab` (default hedges both), `state=`, `prevstate=`,
`analysis_output=` (rarely needed — see above), `report=`. Full detail in `system/weekly_README.md`.

## Step 4 — write the outputs and deliver

The workflow does no file I/O. The caller writes what it returns:

- `report_markdown` → `write_targets.report` (`system/reports/week_{N}.md`)
- `state_json` → `write_targets.state` (`system/state/week_{N}.synthesis.json`)

Then merge the model's sections into the deterministic state file from step 2:

```bash
python3 /home/claude/sunday_scaries/system/merge_state.py --week {N}
```

**Never write `state_json` straight to `week_{N}.json`.** That file is what `state_builder.py`
computed from the Sleeper payloads — standings, rosters, starters, matchups, transactions,
injuries, the verified free-agent set. Overwriting it with model output replaces facts with a
reconstruction, and next week reads the reconstruction as ground truth. `merge_state.py` takes
only `opponent_model`, `keeper_equity`, `decisions_log` and `open_questions` from the agent and
discards anything else it emitted. It keeps a `.prebuild.json` backup and refuses to touch the
deterministic file if the synthesis JSON is missing or malformed.

**Check `state_parse_error` first.** Non-null means the synthesis agent emitted malformed JSON:
write the report anyway and skip the merge — the deterministic state file stands on its own and
is still correct, it just has no opponent model this week. Check `counts` too;
`intelligence_agents_returned` below `dispatched` means agents died and the brief is thinner than
it looks.

Then **send Andrew the files** (report + state JSON) so he holds a copy independent of this
container. That is what makes the next cold start survivable. Post the action card inline in chat —
it should be readable on a phone in thirty seconds. Format: `reference/output_format.md`.

## Step 5 — archive the week into the repo

This is what makes next Tuesday's Step 0/Step 2 actually work — commit this week's outputs to the
same repo Step 0 pulled from, so the *next* brand-new session has something real to read.

```bash
python3 /home/claude/sunday_scaries/system/repo_sync.py commit-and-push \
  --week {N} \
  --report system/reports/week_{N}.md \
  --state system/state/week_{N}.json \
  --synthesis system/state/week_{N}.synthesis.json
```

Run this **after** Step 4's `merge_state.py`, using the merged (post-merge) `week_{N}.json` —
never the pre-merge or synthesis-only file — so the archived copy matches what
`state_builder.py`/`merge_state.py` actually produced, facts intact.

What to expect, and how to react:

| Result | Meaning | Do this |
|---|---|---|
| Exit 0, "pushed ... to origin" | Archived for real. `git log` in the clone is now this month's index. | Nothing further. |
| Exit 0, "SUNDAY_SCARIES_GH_TOKEN is not set" | Expected until Andrew provides a token — this is not an error. The week is committed **locally** in the clone, just not pushed. | Mention it in passing in the brief (not an alarm — this is the documented current state), and note the manual push command the script printed. |
| Exit non-zero, push failed (auth/network) | The commit still exists locally; only the push failed. | See "When it breaks" below — do not lose the week's brief over this. |

Re-running this step for the same week (e.g. after fixing a token problem) is safe — identical
content produces no new commit, and `commit-and-push` still (re)attempts the push, so retrying is
the correct recovery action, not a special case.

---

## Not every question needs 18 agents

The full run is for the Tuesday brief. For a single narrow question, stay inline and cheap:

- **"Who should I start?"** — Steps 1–2 (fetch rosters/matchups, rebuild state), then read the
  lineup out of the state file and reason over it. Weight the first-down bonus; see `reference/scoring.md`.
- **"Should I claim X?"** — Verify he is genuinely a free agent against all ten rosters in
  `raw/rosters.json`, then weigh win-now value against 12th-round keeper equity
  (`reference/keepers.md`) and who picks ahead of Andrew (`system/state/week_N.json` → `waiver_order`).
- **"What changed this week?"** — `state_builder.py --summary` plus the `roster_diff` and
  `transaction_log` sections of the state file.

Escalate to the full workflow when the question is "what should I do this week", or when the answer
depends on modelling what rivals will do.

## Non-negotiable guardrails

- **Availability gate.** Never name a free agent without confirming against all ten rosters in
  `raw/rosters.json` that he is actually unrostered *in this league*. This is the most damaging
  failure the system has: it looks authoritative and wastes a claim. Deterministic check, not vibes.
- **Freshness gate.** Every injury, snap, practice or role claim carries a named source dated inside
  7 days. Wikipedia is banned for anything time-sensitive.
- **Diff, don't snapshot.** The value is in what changed. Load last week's state and compare —
  from the repo clone (`repo_sync.py get-state`, Step 0/2), not from session memory, which does
  not exist between Tuesday firings.
- **Never invent a bye week.** 2026 byes are not populated and are not available from any Sleeper
  endpoint here. `bye_coverage` stays `unknown` until someone hand-enters them. A guessed bye
  silently produces a wrong lineup.
- **Say what is unresolved.** The open questions (waiver clock time, DEF scoring fix, keeper
  deadline, 2026 byes) appear in section 8 of every brief until closed.

## When it breaks

**Usage cap mid-run.** Re-run the identical command with the identical `args`. Completed agents
replay from cache, so a resume only pays for what did not finish. Two rules: pass `week=` explicitly
(a date rollover otherwise changes the week and invalidates the whole cache) and **resume before
midnight UTC** — the run date is embedded in every prompt, so tomorrow's resume re-runs everything.
If Phase 1 keeps dying, run it once to warm the cache on whatever succeeds, then run again.

**Sleeper unreachable / a fetch 403s.** Retry once with `?r=1`. If it still fails, build from the
raw files already on disk — `state_builder.py` degrades to a warning plus an empty section and sets
`meta.degraded`. Say plainly in the brief which section is stale.

**State file missing or stale.** Rebuild from `raw/` (step 2) — it is fully reconstructible. If
`raw/` is also gone, re-fetch (step 1). If a *previous* week's state is missing, run anyway: the
workflow tolerates a missing predecessor, it just loses the diff, and it will say so.

**Rebuilding from nothing (new container, no `system/`).** Ask Andrew for the delivered bundle
(the `.skill` file ships a `bundle/` copy of the whole runtime — see `reference/data_layer.md` for
the restore command) plus the most recent `week_N.json` he was sent. Everything except state and
raw is static and restores byte-for-byte. If nothing at all survives, the league is still fully
reconstructible from the API: this skill's reference files carry every constant, and steps 1–2
rebuild the rest from scratch. Nothing here depends on a chat staying alive.

**GitHub push fails / repo unreachable.** This can happen at either end of the loop — Step 0's
pull or Step 5's push — and neither one should ever cost Andrew the week's brief:

- *Step 0 pull fails* (auth, network, repo renamed/deleted): `repo_sync.py pull` exits non-zero and
  prints why. Fall back to the bundled local snapshot exactly as this skill worked before the repo
  existed — `system/state/week_{N-1}.json` on local disk, if present — and say plainly in the
  delivered brief that continuity may be stale this run because the repo sync failed. Do not block
  the rest of the run on this; a stale-but-present diff target is still better than refusing to
  produce the brief.
- *Step 5 push fails* (bad/expired token, network, GitHub outage): `commit-and-push` still commits
  locally before attempting the push, so the week's archive is **not lost** — it is sitting in
  `repo_clone/` waiting for a working push. Tell Andrew the brief is done and delivered, but this
  week's archive is pending (local-only) and needs either a token fix or a manual
  `git push origin main` from `repo_clone/` once the problem clears. Never treat an archival
  failure as a reason to withhold or redo the brief itself — the brief and the archive are
  independent deliverables.
- *`SUNDAY_SCARIES_GH_TOKEN` unset* is not a failure at all — it is today's expected state until
  Andrew provides a fine-grained PAT (repo: `Aroth2000/sleeper_league`, contents read/write). Treat
  it exactly like the second bullet above: local commit good, push pending, mention it without
  alarm.
- Either way, **verify by checking, not assuming** — `cd repo_clone && git log --oneline -3` shows
  whether this week's commit exists locally, and `git log origin/main --oneline -3` (after a
  `git fetch`) shows whether it actually reached GitHub. Don't report a push as successful without
  having seen `repo_sync.py` print the "pushed ... to origin" line for real.

## Reference files — read on demand, not up front

| File | Read it when |
|---|---|
| `reference/league.md` | you need IDs, roster slots, calendar, waiver mechanics |
| `reference/scoring.md` | valuing any player — the first-down bonus warps everything |
| `reference/teams.md` | naming an owner, a roster_id, or scouting a rival |
| `reference/keepers.md` | any keeper, drop, or long-horizon claim decision |
| `reference/season_phases.md` | deciding posture — week 2 and week 12 get different answers |
| `reference/output_format.md` | writing the brief |
| `reference/data_layer.md` | fetching, the player cache, or restoring the runtime |
