# League constants — Sunday Scaries

Everything here is verified against the live Sleeper API (2026-08-07) unless marked
`UNVERIFIED`. The machine-readable copy is `system/league_config.json`; that file wins if the two
ever disagree, and `raw/league.json` wins over both — it is what the app actually enforces.

## Identity

| Field | Value |
|---|---|
| League name | Sunday Scaries |
| Platform | Sleeper (public read-only API, no auth — just the league ID) |
| Season | 2026 (Year 3) |
| `league_id` (2026) | `1389753893356838912` |
| `previous_league_id` (2025) | `1257451899603402752` |
| `draft_id` 2026 | `1389753893356838913` |
| `draft_id` 2025 | `1257451899603402753` |
| Teams | 10 |
| Scoring type | `2qb` — **SUPERFLEX** |
| Andrew | `roster_id 2`, `user_id 1128203360286429184`, `andrewroth32`, no team name set |

## Roster

Starters (10): **QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX, DEF**
Bench: **6**. Total roster: **16**.

- FLEX takes RB/WR/TE. SUPER_FLEX takes QB/RB/WR/TE — this is why QB is a land grab.
- **Open question:** live 2026 settings show **2 FLEX**; the commissioner's "Season 2 Changes" doc
  says 1. Sleeper is what the app enforces, so assume 2 — but flag any recommendation whose answer
  flips if it is really 1.
- Only 6 bench spots (down from 7 in 2025). Less room to stash. Roster-spot cost is real when
  weighing a speculative claim.

## Calendar

| | |
|---|---|
| Draft | Wednesday **Aug 28, 2026, 7:30pm ET**, snake, 16 rounds; order released 6:30pm |
| Andrew's draft slot | **8** (confirmed) |
| Regular season | weeks 1–14 |
| Trade deadline | **week 13** — a hard wall for consolidation |
| Playoffs | **start week 15**, top **6** teams, weeks 15–17 |
| Season anchor for week math | Tue **Sep 8, 2026** is the Tuesday before Week 1 |

Note the plan doc's "weeks 14–17 are the playoffs" is loose phrasing. Week 14 is the last
regular-season week — the last chance to secure a seed, not a playoff week.

## Waivers — RESOLVED: priority, not FAAB

`league.settings.waiver_type == 1` (Sleeper: 0=rolling, 1=reverse standings, 2=FAAB).

Confirmed empirically against a full real week (2025 week 8, 33 transactions, kept as
`raw/transactions_2025_week8.json`): **zero** transactions carried a non-empty `waiver_budget`, and
three claims carried `settings.priority` (0, 1, 2) — a field Sleeper stamps only on claims that
consumed priority. The 100-unit `waiver_budget` in league settings is Sleeper boilerplate present on
every league and is not in use here.

**Model contention as priority ordering, not bid sizing.**

- Worst record gets priority 1. **Using a successful claim sends that team to the back of the
  queue** — that coupling is the whole mechanic, and it is why `analysis/waiver_contention.py` runs
  a Monte Carlo of the processing order instead of multiplying independent probabilities.
- A *failed* claim costs nothing — Sleeper moves to your next claim in the list. So a long shot
  placed first is free. Order claims by value, not by probability.
- Priority source field: `rosters[].settings.waiver_position`.
- `waiver_day_of_week: 2`, `waiver_clear_days: 2`, `daily_waivers_hour: 0` → claims process
  Tuesday night into Wednesday, at roughly 00:00 ET.
- **UNVERIFIED: the exact clock time.** Treat **Tuesday 18:00 ET** as the safe submission deadline.
  The Tuesday run must land early Tuesday, not Tuesday evening.
- Reverse-standings priority means a rough start *improves* waiver position. Patience is rewarded.

## Trading

Draft-pick trading is **allowed**, which interacts with keepers — a keeper-eligible player's draft
slot can be cashed in for picks from a team that gutted its own draft with keepers.

## Still genuinely open

| Question | Status | Why it matters |
|---|---|---|
| Waiver processing clock time | open | how late the Tuesday run can fire |
| DEF scoring fix applied? | open | historical DEF totals may still be inflated |
| Keeper lock deadline | open | Sleeper shows `keeper_deadline: "1"` with no readable date |
| 2026 NFL bye weeks | open | **not available from any Sleeper endpoint here.** `bye_coverage` stays `unknown`. Never guess one. |
| FLEX 1 vs 2 | resolved by API (2), doc disagrees | positional value and lineup optimisation |

These travel into every brief's section 8 until closed.

## Endpoints (all public, no auth)

```
/v1/state/nfl                                current week — always fetch first
/v1/league/{league_id}                       settings, scoring, roster slots
/v1/league/{league_id}/rosters               rosters, W/L, PF/PA, waiver_position, keepers
/v1/league/{league_id}/users                 owner display names + team names
/v1/league/{league_id}/transactions/{week}   adds/drops/claims/trades + settings.priority
/v1/league/{league_id}/matchups/{week}       per-player points, starters vs bench
/v1/players/nfl/{player_id}                  authoritative name/team/injury for one player
/v1/players/nfl/trending/add?lookback_hours=24&limit=25
/v1/draft/{draft_id}/picks                   full draft results -> keeper costs
```

Never fetch `/v1/players/nfl` — ~5MB, will not pass through WebFetch.
