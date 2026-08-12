# The data layer — fetching, the player cache, and restoring the runtime

The full contract lives in `system/fetch_manifest.md` and is the authority. This is the working
summary plus the cold-start restore procedure, which is the one thing not covered there.

## Why it is split in two

The sandbox proxy returns **403 on CONNECT to `api.sleeper.app`**. No Python, `curl`, or shell HTTP
client in this container can reach Sleeper. Only **WebFetch** can.

```
WebFetch (you, or an agent)   ->  writes raw JSON to system/raw/
players_cache.py ingest       ->  merges identities into players_cache.json
state_builder.py              ->  raw/ + cache  ->  system/state/week_N.json
```

`state_builder.py` contains no HTTP client and never will. Do not add one.

## The extraction prompt

WebFetch pipes every response through a small summarising model, which will happily turn JSON into
prose. Use verbatim, every call:

> Output ONLY a single line of raw JSON, no markdown fences, no commentary, no truncation. Copy
> every field value verbatim from the source. Use null for missing values.

For array endpoints say "Output ONLY a raw JSON array". Strip ```json fences before writing — the
model adds them about half the time.

Three hard-won rules:

1. Never let the model summarise. Always demand verbatim copy.
2. **A spurious 404 is a cache artifact** — responses are cached 15 minutes per URL. Re-request with
   a throwaway query string (`?x=1`, `?r=1`). That recovered 4 of 4 false 404s during the build.
3. **Verify a sample against a second source when the value is load-bearing.** Transcription is
   usually lossless but not guaranteed — one confirmed slip (Hunter Henry came back as WR, not TE)
   is pinned in `OVERRIDES` in `players_cache.py`.

## Exact filenames the builder looks for

```
system/raw/
  state_nfl.json                 required   fetch FIRST, defines {N}
  league.json                    required
  rosters.json                   required
  users.json                     required
  transactions_week{N}.json      in season  (also accepts transactions_{N}.json, transactions.json)
  matchups_week{N}.json          in season
  players_resolved.jsonl         append-only, one JSON object per line
  trending_add.json              optional
  draft_2025_picks.jsonl         one-time seed, already fetched
  draft_2026_picks.jsonl         one-time, right after the Aug 28 2026 draft
  transactions_2025_week8.json   evidence sample, not read by the weekly build
```

Every file is optional at runtime. A missing one produces a warning and an empty section, sets
`meta.degraded = true`, and never a traceback — which means **a wrong filename fails silently**.
Check `meta.sources.missing` and `meta.sources.unparseable` in the output.

## The player cache

`/v1/players/nfl` is ~5MB and will not pass through WebFetch. **Never attempt it.** Build
incrementally instead, from three sources in descending richness:

**a. Draft picks — the bulk seed.** One call to `/v1/draft/{draft_id}/picks` gets ~160 players; ask
for one JSON object per line with `pick_no, round, draft_slot, roster_id, picked_by, player_id` plus
`first_name, last_name, position, team` from the embedded `metadata` block. The 2025 draft alone
resolved 183 of 222 ids in this league.

> **The staleness trap — the biggest correctness risk in this layer.** A draft-pick payload freezes
> a player's team at *that draft's date*. The 2025 draft has Mike Evans on TB and Kenneth Walker on
> SEA; both had moved by 2026 (SF and KC). Draft-seeded entries also carry **no injury data at
> all.** Anything seeded this way is a *name*, not a current *situation*. Find them with
> `players_cache.py stale` and refresh via (c) before trusting any team or injury field.

**b. Transactions — ids only, in this league.** Verified against 2025 week 8: this league's
`/transactions/{week}` responses carry **no metadata block**. Ingest them anyway; new ids land in
the unresolved list, which is exactly the queue for (c).

**c. `/v1/players/nfl/{player_id}` — authoritative.** Verified working through WebFetch. The only
source of current team and injury status. Request:

```
player_id, first_name, last_name, position, team, status, injury_status, injury_body_part,
practice_participation, depth_chart_position, depth_chart_order, age, years_exp, number,
active, search_rank, fantasy_positions, college
```

Append one object per line to `raw/players_resolved.jsonl`, then ingest. This payload is the **only
source permitted to clear a field** — merge-on-write otherwise means information can only ever be
added, so a healed player would keep `Questionable` all season and a cut player would keep his old
team forever. Joe Mixon going unsigned (`team: null`) is the live example.

**Weekly cadence:** re-fetch anyone injured, questionable or newly added (injury status is the
highest-churn field and the one the opponent model leans on hardest), plus every id in
`unresolved_player_ids`. Once before Week 1, work down the `stale` list — Andrew's roster first.

## Commands

```bash
cd /home/claude/sunday_scaries/system

python3 players_cache.py ingest --dir raw
python3 players_cache.py ingest <file> [<file> ...]
python3 players_cache.py lookup <player_id> ...
python3 players_cache.py unresolved --roster-file raw/rosters.json    # want: none
python3 players_cache.py stale      --roster-file raw/rosters.json    # want: short
python3 players_cache.py stats

python3 state_builder.py --week {N} --summary     # build + human-readable print
python3 state_builder.py --dry-run --summary      # inspect, write nothing
python3 state_builder.py --raw-dir ... --out-dir ... --config ...
```

Ingest is idempotent and merge-on-write; running it twice changes nothing. The scripts are pure
stdlib — there is no install step, and there must never be one.

A healthy in-season run shows: all four required files loaded, `0 unresolved`, every starter slot
filled with a real name, and a non-empty `transaction_log`.

## Restoring the runtime into a fresh container

The `.skill` package ships a `bundle/` copy of the entire runtime — scripts, config, player cache,
raw payloads and state as of packaging time. If `/home/claude/sunday_scaries/system` does not exist,
ask Andrew for the `.skill` file (or the standalone bundle) and restore it:

```bash
mkdir -p /tmp/ss && cd /tmp/ss
unzip -o /path/to/sunday-scaries.skill
mkdir -p /home/claude/sunday_scaries
cp -r sunday-scaries/bundle/system /home/claude/sunday_scaries/
cd /home/claude/sunday_scaries/system && python3 state_builder.py --dry-run --summary
```

If that summary prints a sane standings table, the runtime is alive. (Verified end to end from a
clean unzip: builder, cache and the 76-test analysis suite all run straight out of the bundle.)

**Restore to that exact path.** The Python scripts resolve everything relative to their own
location, so they run from anywhere — but `weekly.js` hardcodes
`ROOT = /home/claude/sunday_scaries`. Restoring elsewhere gives you a working data layer and a
broken workflow.

Restore priority when only some pieces survive:

| Piece | Restorable from |
|---|---|
| scripts, `weekly.js`, `league_config.json` | the bundle — static, restores byte-for-byte |
| `raw/*` | re-fetch (step 1 of the runbook) — always current, always cheap |
| `players_cache.json` | the bundle; or rebuild by re-fetching the draft picks and ingesting |
| `state/week_N.json` | the copy Andrew was sent that week; else rebuild from `raw/` |
| everything | worst case: the API rebuilds the world from the league id alone |

The bundle's `raw/` and `state/` are a **snapshot, not truth**. Always re-fetch before acting on
them; check `meta.generated_at` in any state file you restore before treating it as current.
