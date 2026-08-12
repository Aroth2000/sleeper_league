# fetch_manifest.md — the WebFetch ⇄ state_builder contract

**This file is the interface between the two halves of the data layer.**

The sandbox proxy returns **403 on CONNECT to `api.sleeper.app`**, so no Python, `curl`, or
shell HTTP client in this container can reach Sleeper. Only the **WebFetch tool** can.
Therefore the data layer is split:

```
  WebFetch (an agent / the skill)          →  writes raw JSON to system/raw/
  players_cache.py ingest                  →  merges player identities into players_cache.json
  state_builder.py                         →  reads system/raw/ + cache → system/state/week_N.json
```

`state_builder.py` contains **no HTTP client and never will.** If a filename below is
wrong, the builder degrades (warns, emits a null section) rather than crashing — but the
section is silently empty, so **filenames matter.**

---

## The standard extraction prompt

Sleeper returns raw JSON, but WebFetch pipes every response through a small summarising
model. Left to its own devices it will summarise the JSON into prose, which is useless.
Use this prompt verbatim on every call:

> Output ONLY a single line of raw JSON, no markdown fences, no commentary, no truncation.
> Copy every field value verbatim from the source. Use null for missing values.

For endpoints returning arrays, say "Output ONLY a raw JSON array". Then **strip any
```json fences** before writing the file — the model adds them roughly half the time.

Three hard-won rules:

1. **Never let the model summarise.** Always demand verbatim copy.
2. **A spurious 404 is usually a cache artifact.** Responses are cached 15 minutes per URL.
   If a URL you know is valid returns 404, re-request it with a throwaway query string —
   `?x=1`, `?r=1`, `?retry=2`. This recovered 4 of 4 false 404s during the initial build.
3. **Verify a sample against a second source when the value is load-bearing.** WebFetch
   transcription is *usually* lossless but is not guaranteed. See `OVERRIDES` in
   `players_cache.py` for the one confirmed slip (Hunter Henry came back as WR, not TE).

---

## Ordered weekly run

`{N}` = the current NFL week. Steps 1–5 are the weekly core; 6–8 are conditional.

| # | Fetch | Save to `system/raw/` | Required? | Feeds |
|---|---|---|---|---|
| 1 | `GET https://api.sleeper.app/v1/state/nfl` | `state_nfl.json` | **yes** | current week — run this first, it tells you what `{N}` is |
| 2 | `GET https://api.sleeper.app/v1/league/1389753893356838912` | `league.json` | **yes** | scoring, roster slots, waiver settings, playoff/deadline weeks |
| 3 | `GET https://api.sleeper.app/v1/league/1389753893356838912/rosters` | `rosters.json` | **yes** | rosters, starters, W/L, PF/PA, **`settings.waiver_position`** |
| 4 | `GET https://api.sleeper.app/v1/league/1389753893356838912/users` | `users.json` | **yes** | owner display names + team names |
| 5 | `GET https://api.sleeper.app/v1/league/1389753893356838912/transactions/{N}` | `transactions_week{N}.json` | **yes** in season | every add/drop/waiver/trade **and which priority was used** |
| 6 | `GET https://api.sleeper.app/v1/league/1389753893356838912/matchups/{N}` | `matchups_week{N}.json` | in season | per-player points; starters vs bench — the factual basis for *performance pressure* |
| 7 | `GET https://api.sleeper.app/v1/players/nfl/{player_id}` | append to `players_resolved.jsonl` | as needed | names, **current NFL team**, **injury_status** |
| 8 | `GET https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=25` | `trending_add.json` | optional | league-wide hot adds — proxy for who is about to be claimed |

**Step 1 runs first.** Everything else keys off the week it reports.

### After fetching, always run — in this order

```bash
cd /home/claude/sunday_scaries/system
python3 players_cache.py ingest --dir raw     # merge identities FIRST
python3 state_builder.py --summary            # then build state
```

Order is not optional. `state_builder.py` reads `players_cache.json` as it exists on disk;
it does not ingest raw payloads itself (beyond noting rostered ids). Building before
ingesting yields a state file full of `UNKNOWN(12474)`.

---

## Step 7 in detail — the player cache, and the staleness trap

The full dump `/v1/players/nfl` is ~5MB and **cannot come through WebFetch intact.** Do not
try. Build the cache incrementally instead. Three sources, in descending richness:

**a. Draft picks — the bulk seed.** One call gets ~160 players:

```
GET https://api.sleeper.app/v1/draft/1257451899603402753/picks   → raw/draft_2025_picks.jsonl
```

Ask for one JSON object per line with `pick_no, round, draft_slot, roster_id, picked_by,
player_id` and, from the embedded `metadata` block, `first_name, last_name, position, team`.
This alone resolved 183 of 222 ids in this league.

> **⚠ The staleness trap — the single biggest correctness risk in this layer.**
> A draft-pick payload freezes a player's team at *that draft's date*. The 2025 draft has
> Mike Evans on **TB** and Kenneth Walker on **SEA**. Both had moved by 2026 (SF and KC).
> Draft-seeded entries also carry **no injury data at all.**
> Anything seeded this way is a *name*, not a current *situation*.
> Find them with `python3 players_cache.py stale --roster-file raw/rosters.json`
> and refresh via (c) before trusting any team or injury field.

**b. Transaction payloads — ids only, in this league.** Verified against 2025 week 8:
this league's `/transactions/{week}` responses carry **no `metadata` block**, so they
contribute ids but no names. Ingest them anyway — new ids land in the unresolved list,
which is exactly the queue for (c).

**c. The per-player endpoint — authoritative.** `GET /v1/players/nfl/{player_id}` works
through WebFetch (verified) and is the **only** source of current team and injury status.
Request these fields:

```
player_id, first_name, last_name, position, team, status, injury_status,
injury_body_part, practice_participation, depth_chart_position, depth_chart_order,
age, years_exp, number, active, search_rank, fantasy_positions, college
```

Append one JSON object per line to `raw/players_resolved.jsonl`, then ingest.

This payload is treated as **authoritative**: it is the only source permitted to *clear* a
field. That matters more than it sounds. Merge-on-write otherwise means information can
only ever be added, so a player who heals would keep `Questionable` for the rest of the
season and a cut player would keep his old team forever. Joe Mixon going unsigned
(`team: null`) is the live example. Partial payloads can never blank anything.

**Weekly cadence for step 7:**

- Every week: re-fetch anyone **injured, questionable, or newly added** — injury status is
  the highest-churn field and the one the opponent model leans on hardest.
- Every week: any id appearing in `unresolved_player_ids` in the state file.
- Once before Week 1: work down the `stale` list, Andrew's roster first, then the other
  nine. ~104 rostered players still carry draft-vintage data as of this writing.

---

## Endpoints deliberately NOT in the weekly loop

| Endpoint | Why not |
|---|---|
| `/v1/players/nfl` | ~5MB, cannot pass through WebFetch. Never attempt. |
| `/v1/draft/1257451899603402753/picks` | One-time seed; 2025 draft results do not change. Already fetched. |
| `/v1/draft/1389753893356838913/picks` | **Fetch once, right after the Aug 28 2026 draft.** Save as `raw/draft_2026_picks.jsonl`. Reseeds the cache with current-season teams and establishes every player's 2027 keeper cost. |
| `/v1/league/{id}/drafts`, `/traded_picks` | Only when auditing pick ownership for a trade. |

---

## Resolved by real data — do not re-litigate

**Waivers are priority-based, not FAAB.** This was the top open question in the plan
document. Settled empirically against 33 real transactions from 2025 week 8
(`raw/transactions_2025_week8.json`, kept as evidence):

- **Zero** transactions carried a non-empty `waiver_budget` — across the entire week.
- Three claims carried `settings.priority` (values 0, 1, 2), which Sleeper stamps *only*
  on claims that consumed priority.
- `league.settings.waiver_type == 1` = reverse-standings rolling priority.

The 100-unit `waiver_budget` field in league settings is a Sleeper default that this league
never uses. **Model contention as priority ordering, not bid sizing.**

`settings.priority` is the field to watch weekly: it is the ground truth for who spent
priority and therefore who dropped to the back of the queue.

### Still genuinely open

- **Waiver processing clock time.** `waiver_day_of_week: 2`, `waiver_clear_days: 2`. The
  day is pinned; the wall-clock hour is not. Assume a **Tuesday 18:00 ET** submission
  deadline until confirmed.
- **2026 NFL bye weeks.** Not populated in `league_config.json`
  (`nfl_bye_weeks_2026.byes`), and **not available from any Sleeper endpoint in this
  manifest.** Bye-week coverage stays `status: "unknown"` until someone hand-enters the
  32-team map. Deliberately not guessed — a wrong bye week silently produces a wrong
  lineup, which is worse than an admitted gap.
- **FLEX count.** Live 2026 settings show 2 FLEX; the Season-2 rules doc says 1. The
  builder reads whatever `league.json` actually reports and flags a mismatch.
- **DEF scoring fix.** Commissioner flagged it; not confirmed applied.

---

## Filename reference (exact strings the builder looks for)

```
system/raw/
  state_nfl.json                 step 1   required
  league.json                    step 2   required
  rosters.json                   step 3   required
  users.json                     step 4   required
  transactions_week{N}.json      step 5   also accepts transactions_{N}.json, transactions.json
  matchups_week{N}.json          step 6
  players_resolved.jsonl         step 7   append-only, one object per line
  trending_add.json              step 8
  draft_2025_picks.jsonl         one-time seed
  draft_2026_picks.jsonl         one-time, after the Aug 28 draft
  transactions_2025_week8.json   evidence sample; not read by the weekly build
```

Every one of these is optional at runtime. A missing file produces a warning plus an empty
section, and `meta.degraded` flips to `true` — never a traceback. Check
`meta.sources.missing` and `meta.sources.unparseable` in the output to see what was lost.

---

## Verifying a run

```bash
python3 state_builder.py --week {N} --summary     # human-readable
python3 state_builder.py --week {N} --dry-run     # inspect without writing
python3 players_cache.py stats
python3 players_cache.py unresolved --roster-file raw/rosters.json   # want: none
python3 players_cache.py stale     --roster-file raw/rosters.json    # want: short
```

A healthy in-season run shows: all four required files loaded, `0 unresolved`, every
starter slot filled with a real name, and a non-empty `transaction_log`.
