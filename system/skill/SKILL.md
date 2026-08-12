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
  system/merge_state.py         folds the agent's opponent_model/keeper_equity/decisions_log/
                                open_questions into week_N.json without overwriting facts
  system/weekly.js              the 18-agent workflow (Workflow tool, NOT node)
  system/analysis/*.py          scoring, opponent_pressure, waiver_contention, keeper_equity
                                (+ test_analysis.py — 76 tests, run it after any edit)
  system/raw/                   fetched Sleeper JSON lands here
  system/state/week_N.json      the memory. week_0.json is the preseason baseline.
  system/reports/week_N.md      the delivered brief
```

## Two hard environment facts

1. **Nothing in this sandbox can reach `api.sleeper.app` except the WebFetch tool.** The proxy
   returns 403 on CONNECT. Never write or run Python/curl that calls Sleeper — it will fail.
   WebFetch writes raw JSON to disk; Python parses it. That split is not negotiable.
2. **`/players/nfl` (~5MB) will not come through WebFetch.** Never attempt it. The player cache is
   built incrementally from draft-pick payloads and per-player calls. See `reference/data_layer.md`.

## Step 0 — orient before doing anything

```bash
ls /home/claude/sunday_scaries/system/state/          # what weeks exist?
python3 /home/claude/sunday_scaries/system/state_builder.py --dry-run --summary
```

That summary prints the current week, waiver order, Andrew's lineup and which raw files are
missing — it is the fastest read on where the system stands. Then branch:

| What you find | Do this |
|---|---|
| `system/` missing entirely | **Cold start.** See "Rebuilding from nothing" below. |
| State files exist, newest is last week | Normal run. Go to Step 1. |
| Newest state is this week, generated today | Already ran. Show the existing `reports/week_N.md` unless asked to re-run. |
| State exists but `meta.degraded == true` | A fetch was missing. Check `meta.sources.missing`, re-fetch those, rebuild. |
| Only `week_0.json` and it is week 1 | Correct and expected. Week 0 is the preseason baseline, not a played week. |

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

## Step 2 — build state (deterministic, no model)

```bash
cd /home/claude/sunday_scaries/system
python3 players_cache.py ingest --dir raw     # identities FIRST
python3 state_builder.py --week {N} --summary # then state
```

Order is not optional — building before ingesting yields a state file full of `UNKNOWN(12474)`.
Then check the cache is clean:

```bash
python3 players_cache.py unresolved --roster-file raw/rosters.json   # want: none
python3 players_cache.py stale      --roster-file raw/rosters.json   # want: short
```

Anything unresolved goes back to step 1 line 7. `stale` means the entry was seeded from the 2025
draft, so its **team and injury fields are 2025-vintage and must not be trusted** — Mike Evans is
cached from that draft as TB when he is on SF. Refresh stale entries for Andrew's roster and for
anyone you are about to recommend.

## Step 3 — run the workflow

Invoke with the **Workflow tool**, absolute path. It is not a node program; do not `node` it.

```
Workflow: /home/claude/sunday_scaries/system/weekly.js
args:     week={N}
```

18 agents: 15 sonnet in parallel (9 opponent models, 4 topic-sliced news sweeps, free-agent board,
my-team read), then 2 opus (waiver contention, trade board), then 1 opus synthesis.
Optional args: `waivers=priority|faab` (default hedges both), `state=`, `prevstate=`, `report=`.
Full detail in `system/weekly_README.md`.

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
- **Diff, don't snapshot.** The value is in what changed. Load last week's state and compare.
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
