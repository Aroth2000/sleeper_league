---
name: sunday-scaries
description: Runs Andrew's Sunday Scaries fantasy football system (Sleeper, 10-team superflex half-PPR-plus-first-down keeper league) end to end from a fresh session with no prior memory. Use for the scheduled Tuesday and Sunday-AM runs, the weekly fantasy brief, or any in-season question about this league - waiver claims, start/sit and lineup help, drop candidates, trade offers, opponent scouting, keeper decisions and keeper equity. Triggers - tuesday update, sunday scaries, weekly fantasy brief, waiver recommendations, what should I claim, who should I start, start/sit, lineup help, fantasy trade offers, keeper board, league intel.
---

# Sunday Scaries — the weekly automated system

A fresh Claude session, fired on a schedule, that produces the week's action plan for Andrew's
Sleeper team: **lineup, ordered waiver claims, drop candidates, trade offers, an intel read on the
nine rivals, and — first — a graded review of how last week's recommendations actually turned out.**
That last part is what makes this a *learning* system, not just a weekly report generator.

## The golden rule + where memory lives

A scheduled firing **remembers nothing on its own** — it's a fresh session. Two durable stores hold
everything, and knowing which is which is the whole trick:

- **Code + reference** live in the GitHub repo `github.com/Aroth2000/sleeper_league` — this runbook,
  the Python, the config, the docs. Clone it to read; it changes rarely.
- **Weekly memory** — last week's decisions, their grades, the running lessons, the rolling
  hit-rate — lives in the **season-log artifact's database**, which a scheduled cloud run can read
  AND write directly with the Artifact tool, **no push and no linked computer needed**:
  **`ARTIFACT_URL = https://claude.ai/code/artifact/004d6522-cc50-4a98-b4f6-b0002aab10e1`**
  Read it with the Artifact `read_db` action, write it with `write_db` (collections `weeks`,
  `lessons`, `meta`). This is the primary memory the learning loop runs on, and it is bridge-proof.
  The GitHub `data/week_NN/` archive is a secondary, best-effort copy — nice for browsing, not
  required, since pushing from a cloud session is unreliable.

Never rely on "what we discussed last time"; read from these two stores and from freshly fetched
Sleeper data. There is no last time.

## Runtime & two hard environment facts

This runs in an Anthropic cloud session. It may also be linked to Andrew's computer (the
`mcp__remote-devices__*` tools) — that link is used **only to push to GitHub** and is optional; the
brief itself never depends on it.

1. **Only the WebFetch tool can reach `api.sleeper.app`.** The sandbox proxy 403s direct
   curl/python HTTP to Sleeper. WebFetch pulls the JSON, Python parses it from disk. That split is
   not negotiable. (If a run is executing on the linked computer via `device_bash`, that shell's
   network *may* reach Sleeper directly — try it, but WebFetch is always the reliable fallback.)
2. **`/players/nfl` (~5MB) will not come through WebFetch.** Never attempt it. The player cache is
   built incrementally from draft payloads and per-player calls (`.../players/nfl/{id}`).

`RUN_DIR` below = the working clone this run operates in. In a scheduled cloud session, make one:

```bash
RUN_DIR=~/sleeper_run
rm -rf "$RUN_DIR" && git clone --depth 50 https://github.com/Aroth2000/sleeper_league.git "$RUN_DIR"
cd "$RUN_DIR/system"
```

A public clone for *reading* always works from the cloud. Pushing is Step 8's problem.

---

## STEP 0 — orient

```bash
python3 state_builder.py --week AUTO --summary --dry-run   # after Step 1 fills state_nfl.json; on the
                                                           # very first orient, just read what exists
ls state/ ; ls data/            # what weeks exist locally and in the archive?
```

Determine the current week from `raw/state_nfl.json` (fetched first in Step 1) — never guess it from
the calendar. Then branch:

| What you find | Do |
|---|---|
| Newest archived week is last week | Normal run — continue. |
| A brief for *this* week already exists (`data/week_NN/`) and nothing material changed | Say so; re-run only if asked or if news broke. |
| `data/` has only `week_00` and it is week 1 | Correct — week 0 is the preseason baseline, not a played week. Proceed with no prior-week diff and say so. |
| Repo clone failed | Fall back to any local `system/state/` snapshot; say plainly in the brief that continuity may be stale this run. Never fail silently. |

## STEP 1 — fetch (WebFetch only)

Fetch these into `RUN_DIR/system/raw/`. Run `state/nfl` first — it defines `{N}`. On every WebFetch
use this exact extraction prompt or the summariser turns JSON into prose:

> Output ONLY a single line of raw JSON, no markdown fences, no commentary, no truncation. Copy every field value verbatim from the source. Use null for missing values.

| # | URL | Save as |
|---|---|---|
| 1 | `.../v1/state/nfl` | `state_nfl.json` |
| 2 | `.../v1/league/1389753893356838912` | `league.json` |
| 3 | `.../league/1389753893356838912/rosters` | `rosters.json` |
| 4 | `.../league/1389753893356838912/users` | `users.json` |
| 5 | `.../league/1389753893356838912/matchups/{N}` | `matchups_week{N}.json` |
| 5b | `.../league/1389753893356838912/matchups/{k}` for EVERY completed week k = 1..N-1 | `matchups_week{k}.json` (per-player points; the trade analysis and grading both need the history) |
| 5c | `.../draft/1389753893356838913/picks` — **only if `raw/draft_2026_picks.json` is missing** (it is committed; the draft never changes) | `draft_2026_picks.json` |
| 6 | `.../league/1389753893356838912/transactions/{N}` | `transactions_week{N}.json` |
| 7 | `.../players/nfl/trending/add?lookback_hours=24&limit=25` | `trending_add.json` |
| 8 | `.../players/nfl/{id}` for injured / new / unresolved ids | append to `players_resolved.jsonl` |

A 404 on a URL you know is good is a 15-minute cache artifact — retry with `?r=1`. Strip any ```json
fences before writing. Wrong filename = silently empty section, not an error.

## STEP 2 — resolve the player cache

```bash
python3 players_cache.py ingest --dir raw
python3 players_cache.py unresolved --roster-file raw/rosters.json   # want: none
python3 players_cache.py stale      --roster-file raw/rosters.json   # want: short
```

Any unresolved id → fetch `.../players/nfl/{id}` (Step 1 line 8) and re-ingest. `stale` entries were
seeded from the 2025 draft, so **their team/injury fields are a year old and must not be trusted** —
refresh every stale player on Andrew's roster and anyone about to be recommended. New 2026 rookies
(e.g. the late-round picks) usually need one per-id fetch each the first time they appear.

## STEP 3 — build state + the deterministic analysis baseline

```bash
python3 repo_sync.py get-state --week {N-1}     # stage last week's real state from the archive, if any
python3 state_builder.py --week {N} --summary   # raw/*.json -> state/week_{N}.json (facts only)
python3 analysis/build_analysis_output.py state/week_{N}.json
```

`state_builder.py` produces the non-hallucinable facts (standings, rosters, starters, matchups,
injuries, the **code-verified** free-agent set, bye coverage — 2026 byes are now populated in
`league_config.json`). `build_analysis_output.py` produces `state/week_{N}_analysis_output.json`:
opponent positional pressure, predicted rival waiver claims, a Monte-Carlo contention report on who
survives to Andrew's waiver slot, and the keeper-equity board (N-1 rule). These numbers are the
baseline every qualitative judgment must cite and may refine — never contradict silently.

## STEP 4 — grade last week (the learning loop) ★

Before making any new call, score the last one. Read last week's decisions from the season-log DB —
Artifact `read_db` on `ARTIFACT_URL`, collection `weeks`, doc `week_{N-1}` (its `decisions` array).
For each open decision, determine what actually happened from this week's fetched data and mark an
`outcome` (`hit` / `miss` / `push`):

- **Waiver claim recommended** → did Andrew's roster gain that player (check `transaction_log` /
  roster diff)? Did the player produce? Was he even still available when Andrew's slot came up
  (compare to the contention model's prediction)?
- **Start/sit call** → did the started player out-score the benched alternative this week
  (`matchups_week{N}`)? Log the points swing, positive or negative.
- **Drop / hold** → did the dropped player get claimed by a rival and hurt us? Did the held player
  justify the roster spot?
- **Trade floated** → did it happen, get countered, or get ignored?

Write the graded results **back to the DB**: `write_db` `weeks/week_{N-1}` with each decision's
`outcome` set (add a short `grade_note`); append one `lessons` doc per notable miss/hit
(`write_db` a new doc `{week, text, created}`); and update `meta/season` with the new rolling
hit-rate. Keep a rolling hit-rate: fraction of graded waiver/start calls that were correct.
**Feed these lessons into Step 6** — e.g. "we've over-valued Week-1 target
share three times; discount it," or "our contention model under-predicted jomud's RB appetite."
This is the mechanism by which the system gets better; do not skip it, and do not let it become
self-congratulatory — the misses are the point.

If there is no prior `decisions.json` (first run of the season), say so and skip grading.

## STEP 5 — research (news + opponents), gated

Gather the qualitative layer. For a full weekly brief, fan this out to parallel subagents (the Agent
tool) to stay fast and keep each one's context clean — a reasonable split: one agent for
Andrew's-roster news, one or two for leaguewide injury/role/depth-chart news by position group, and
one to scout the rivals most likely to contest Andrew's waiver targets (use the pressure model to
pick which rivals matter). Two gates are absolute:

- **Availability gate.** Never name a "free agent" without confirming against all ten rosters in
  `raw/rosters.json` that he is genuinely unrostered *in this league*. The most damaging failure the
  system has is recommending a claim for someone already rostered — deterministic check, not vibes.
- **Freshness gate.** Every injury/snap/practice/role claim carries a named source dated within 7
  days. No Wikipedia for anything time-sensitive. Prefer the WebFetch/WebSearch tools; if a domain
  is blocked, find another source rather than routing around the restriction.

## STEP 5b — trade analysis (deterministic search, then research, then re-run) ★

The trade board is code, not vibes: `analysis/trade_analysis.py` values every rostered player
(this season's points shrunk toward a draft-round prior), builds each team's best lineup week by
week through the fantasy playoffs (byes, injuries and a first-order injury penalty for thin depth
all included), and searches every 1-for-1 and 2-for-1 / 1-for-2 trade with all nine rivals. A trade
is proposed only if **your** lineup gains, the **other side's lineup doesn't lose**, and the
perceived-value swap is close enough that they might say yes. It also prints 2027 keeper cost and
value for every player involved, and always reports straight RB-for-WR and WR-for-RB swaps.

It does not read the news. The research feeds it through a flags file. Run from `system/`:

```bash
# 0. every rostered id must be identified first (the script warns loudly otherwise):
#    fetch /players/nfl/{id} for each, append to raw/players_resolved.jsonl
# 1. who needs a health/role check before the numbers can be trusted?
python3 analysis/trade_analysis.py --raw raw --me 2 --candidates-only
# 2. RESEARCH those players (Agent waves, freshness gate: source dated within 7 days), then write
#    state/week_{N}_flags.json  -- format in the docstring of trade_analysis.py:
#    {"<player_id>": {"out_weeks": [4,5]} | {"out_through": 6} | {"season_ending": true}
#                     | {"ros_mult": 1.1} | {"ppg_override": 17} | {"untouchable": true}, "note": "..."}
#    Put Andrew's must-keep players in as {"untouchable": true}.
# 3. the real run (~20 seconds):
python3 analysis/trade_analysis.py --raw raw --me 2 --flags state/week_{N}_flags.json \
    --out state/week_{N}_trades.json --md reports/week_{N}_trades.md
```

Rules for using the output in the brief (part ⑤):
- **Present it, don't oversell it.** Lead with the best 2-3 trades and the straight-swap sections.
  Say what each side gains in lineup points per week and the fairness line. If the honest answer is
  "no trade clears the bar", say that.
- **Availability + freshness gates apply.** Re-check every player in a proposed trade against the
  latest injury news; a flag you have not verified this week must be labelled as unverified.
- **Never claim a trade will be accepted.** Andrew sends offers in Sleeper himself; give him the
  pitch (who, what, why they say yes).
- **Log them for grading.** Add the top 3 to this week's `decisions` (`type: "trade"`,
  `outcome: null`). Next Tuesday's Step 4 grades them: did the trade happen (`transactions` of type
  `trade`), and how did the players involved actually score after.
- The value model is a heuristic on 3-4 games of data. When a proposal hinges on a small
  difference (under ~1 point a week), say so.

## STEP 6 — synthesize the brief

Produce the action plan, weighting: (a) this league's scoring — the 0.5/first-down bonus rewards
possession/chain-movers over boom-bust deep threats (see `reference/scoring.md`); (b) the season
phase posture (`reference/season_phases.md` — week 2 and week 12 get different answers); (c) the
**lessons from Step 4**; (d) the deterministic baseline from Step 3; (e) keeper equity — every
in-season add carries hidden 2027 keeper value at an R12 price (`reference/keepers.md`, N-1 rule).

The brief has these parts (format: `reference/output_format.md`): **①** last week graded + rolling
hit-rate, **②** lineup / start-sit with the points reasoning, **③** ordered waiver claims with the
survival odds and the keeper-equity note, **④** drop candidates, **⑤** trade board (from Step 5b: best trades any shape + straight RB/WR swaps + buy-low and sell-high lists), **⑥** rival
intel (what each contender is about to do), **⑦** open questions still unresolved, **⑧** the
machine-readable `decisions.json` for THIS week (so next week's Step 4 can grade it).

## STEP 7 — deliver to Andrew

Send Andrew the brief so he holds it independent of any container: SendUserFile the report, and post
a phone-readable action card inline (30-second read). On a scheduled run, the completion
notification carries the headline. This delivery is the run's core value and must happen **even if
Step 8's archive push fails.**

## STEP 8 — persist memory (primary), then archive (best-effort)

**Primary — write this week's memory to the season-log DB.** Bridge-independent, always works from a
cloud run, and it is what makes next week's Step 4 possible:
- Artifact `write_db` `ARTIFACT_URL` collection `weeks` doc `week_{N}` = `{week, season, opponent,
  result, generated, decisions}` — the `decisions` array is this week's calls, each with
  `outcome: null`, ready to be graded next week.
- Artifact `write_db` `meta/season` = `{current_week, record, hit_rate, hit_rate_sub, updated}`.
- **Mirror the DB to an owned copy.** `read_db` all collections and write them as JSON under
  `system/state/db_mirror/` (carried by the best-effort archive push below), and SendUserFile the
  export to Andrew on request. This guarantees a portable, version-controlled copy that survives even
  if the artifact is ever deleted — the DB is the fast live store, this JSON is the backup Andrew owns.

Do this even if every other step failed — a delivered brief with its decisions saved is a complete
run.

**Secondary — GitHub archive (best-effort, for browsable history).** Merge judgment into the facts
file, then try to push; it will often fail from the cloud, and that is fine because the DB above
already holds the memory:

```bash
python3 merge_state.py --week {N}   # folds opponent_model/keeper_equity/decisions_log/open_questions
                                    # into the FACTS file without overwriting them; keeps a backup
```

Never write synthesis output straight over `week_{N}.json` — that file is the deterministic facts;
`merge_state.py` takes only the four judgment sections and discards the rest. Then archive (this is
what makes next week's Step 0/3/4 work):

```bash
export SUNDAY_SCARIES_GH_TOKEN="$(cat <token-file>)"   # see 'The push token' below
python3 repo_sync.py commit-and-push --week {N} \
  --report reports/week_{N}.md --state state/week_{N}.json --synthesis state/week_{N}.synthesis.json
# also archive this week's decisions.json and lessons.md into data/week_{N}/
```

**The push, honestly.** A cloud session cannot push to GitHub directly — the git proxy blocks it
unless the repo is added to the session's authorized sources. Two ways it actually lands:
- *Authorized sources configured* → `commit-and-push` works from the cloud. Best case; nothing else needed.
- *Linked computer available* → run the commit-and-push through `device_bash` on the linked machine
  (its git can push), reading the token from the gitignored file on disk there.
- *Neither right now* → the commit still exists locally; the **brief was already delivered in Step
  7**. Say "archive deferred, will sync next run," and the next run re-derives from live data anyway.
  Never withhold or redo the brief over an archival failure — they are independent deliverables.

Verify by checking, not assuming: `git log origin/main --oneline -3` after a fetch shows whether the
commit actually reached GitHub.

**The push token.** Auth is a fine-grained GitHub PAT (repo `Aroth2000/sleeper_league`, contents
read+write), never hardcoded and never written into `.git/config`. `repo_sync.py` reads it only from
`SUNDAY_SCARIES_GH_TOKEN` and passes it inline on the one push URL. On the linked computer it lives
in a gitignored file (e.g. `.secrets/gh_token.txt`) outside anything that gets committed.

---

## Not every question needs the full run

For a single narrow ask, stay inline and cheap: fetch what's needed (Steps 1–3), read the answer out
of the state file, reason over it with the scoring/keeper references. Escalate to the full run only
for "what should I do this week" or anything that depends on modelling rival behavior.

## Guardrails (non-negotiable)

- **Availability gate** and **Freshness gate** — as in Step 5.
- **Diff, don't snapshot.** The value is in what changed since last week; load the prior state from
  the archive and compare.
- **Byes are populated** (`league_config.json` → `nfl_bye_weeks_2026`, cross-verified). Week 11 is a
  6-team bye; week 12 has none. Still sanity-check a starter isn't on bye before recommending him.
- **Say what's unresolved.** Open questions (exact waiver clock time; whether the DEF scoring fix
  shipped) ride in section ⑦ of every brief until closed.
- **Keeper math is N-1.** A repeat keep costs one round cheaper in number than last year (floored at
  R1 = final year); a first-time keep costs his draft round; FA adds cost R12. Never quote the old
  flat model.

## When it breaks

- **Sleeper fetch 403/404** → retry once with `?r=1`; else build from raw already on disk
  (`state_builder.py` degrades to a warning + `meta.degraded`) and name the stale section.
- **A subagent dies** → the brief is thinner, not wrong; note which intel is missing.
- **Usage cap mid-run** → resume; pass `week={N}` explicitly so a date rollover doesn't shift it.
- **Push fails** → Step 8 above; brief still ships.

## The comprehensive research sweep (Tuesday, and on demand)

Goal: current, sourced coverage of **every relevant offensive player** — all rostered players,
recently dropped players, waiver-pool names, and the broader skill-position pool across all 32 NFL
teams — without exhausting the web-search budget. The trick is breadth from BULK data, depth (web
search) only where something moved.

1. **Bulk ingest — a handful of fetches that cover everyone.** Pull structured leaguewide data and
   save raw to `raw/`, parse with Python:
   - Sleeper: all 10 rosters (who's rostered / just dropped), every player's `injury_status`,
     transactions, trending adds/drops.
   - ESPN public JSON (reachable via WebFetch, verified): leaguewide injuries
     `https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries`; team depth charts and
     rosters via ESPN's team endpoints.
   - Weekly usage (snaps / routes / target & carry share): a bulk source (e.g. nflverse weekly data);
     verify reachability each run and fall back to per-team ESPN box-score pulls if one is down.
   This layer is cheap and covers every player — it is the breadth, and it cannot be throttled the way
   per-player search can.

2. **Deterministic flagging.** From the bulk data compute who MATERIALLY changed: a snap/target-share
   jump, a new starter, an injury/IR/suspension, a depth-chart climb, an NFL-team change, or a spike
   in adds/drops. Leaguewide this is typically 30–60 players, not 500.

3. **Targeted deep web-search fan-out — POOLED / BATCHED.** One agent per flagged player, each running
   the SAME fixed protocol: depth chart, snaps/routes/touches + trend, teammate-injury opportunity
   shifts, practice-report status, role/scheme notes, transactions/suspensions — every claim carrying
   a source dated within 7 days. **Launch in waves of ~10–15 (next wave starts as the prior finishes),
   never all at once, to stay under the shared search rate/budget.** If using the Workflow tool, cap
   `parallel()` concurrency to the wave size. Breadth already came from step 1, so this expensive step
   only ever runs on the small flagged set.

4. **Store a dossier per player to the DB** — collection `players`, doc id = Sleeper `player_id`,
   `{name, pos, team, updated, injury_status, snaps, target_share, role_note, source, source_date}`.
   Every player the bulk layer covered gets the structured fields; flagged players also get the
   researched `role_note`. The brief is synthesized from the decision-relevant subset while every
   other dossier sits queryable in the DB for trades and scouting.

On demand ("do research"): the same sweep runs whenever Andrew asks, not only on the Tuesday schedule.
For a single player or team, run just steps 1+3 scoped to them.

## Reference files — read on demand

| File | When |
|---|---|
| `reference/league.md` | IDs, roster slots, calendar, waiver mechanics |
| `reference/scoring.md` | valuing any player — the first-down bonus warps everything |
| `reference/teams.md` | naming an owner / roster_id / scouting a rival |
| `reference/keepers.md` | any keeper, drop, or long-horizon claim (N-1 rule, keeper equity) |
| `reference/season_phases.md` | posture — week 2 ≠ week 12 |
| `reference/output_format.md` | writing the brief |
| `reference/data_layer.md` | fetching, the player cache, restoring the runtime |
| `../../docs/draft_report_2026.md` | how the season started — each team's draft, strengths, holes |
