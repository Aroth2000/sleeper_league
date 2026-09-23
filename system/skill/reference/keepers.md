# Keeper rules and keeper equity

## ✅ RESOLVED 2026-08-24 — cost rule corrected, R1-escalation conflict resolved, full recompute done

Andrew corrected the cost rule: **if a player was kept in the previous year, the cost to keep him
again is N-1** (one round cheaper in number each consecutive year kept), not flat/carried-forward as
previously documented in this file. He also resolved the conflict this surfaced: **"1st-round picks
are not keeper-eligible" refers only to a player's *original* draft round** — it does not block a
keeper cost from aging up into Round 1. So Jahmyr Gibbs, Bijan Robinson, and Amon-Ra St. Brown are
all validly kept at R1 for 2026 (none of them was an original 1st-round pick; they aged there via two
years of N-1 escalation from an original Round 2 cost).

**Real consequence, not just a label change: this is each of their LAST eligible keeper year.**
Round 1 is the cost floor — there is no R0 to escalate to next time, and an original-1st-round-only
restriction doesn't create an exception. If any of the three is kept again in 2027 the math has
nowhere to go, so **Gibbs, Bijan Robinson, and Amon-Ra St. Brown all become keeper-ineligible after
this season**, regardless of the separate 3-consecutive-year cap. Flag this now in each team's
keeper-equity tracking so it isn't rediscovered at next year's deadline.

**This also changes which actual pick number gets forfeited, not just the cost label** — a player's
keeper round determines which of that team's picks is forfeited, so escalating a cost from R12 to R11
(for example) moves the forfeited pick number itself, not just what it's called. That cascaded through
the entire 160-pick draft sequence, `league_reference.md` §8/§9, `keeper_cost_board.txt`, and
`draft_board_2026.md` — all four have been recomputed against this corrected rule as of 2026-08-24.

## The rules (as written by the commissioner, cost rule corrected 2026-08-24)

- Keep up to **3 players**.
- Cost to keep, **first time a player is kept**: the round he was drafted the previous year.
- Cost to keep, **every consecutive year after that**: **N-1** — one round cheaper in number (more
  expensive in value) than what he cost last year. *(Corrected 2026-08-24 — previously documented as
  flat/carried-forward at the same round indefinitely. That was wrong.)*
- **1st-round picks are not keeper-eligible** — applies only to a player's *original* draft round.
  An escalated keeper cost reaching R1 is valid; that player simply has no further eligible year.
- A player added off **waivers or free agency who was never drafted costs a 12th-round pick** (flat —
  nothing suggests this escalates the way a drafted-then-kept player's cost does; still unconfirmed,
  low-stakes since it's already the cheapest keeper-eligible round in practice).
- **No player may be kept more than 3 consecutive years.**
- Keeping a player forfeits that round's pick in the coming draft — **the round as escalated this
  year**, not last year's round.
- Draft-pick trading is allowed, which interacts with all of the above.
- **UNVERIFIED:** the lock deadline. Sleeper carries `keeper_deadline: "1"` with no readable date —
  confirm with tlekes.

## Full 2026 keeper board — final, corrected N-1 rule applied everywhere in this project

Verified against the actual 2025 Sleeper draft record (`system/raw/draft_2025_picks.jsonl`, `is_keeper`
flag) for who was genuinely a repeat keeper vs. a first-time keep. 13 of the league's 29 locked 2026
keepers were also kept in 2025, so all 13 escalate. The other 16 were drafted fresh in 2025 (first
keep), so their cost is unaffected — same as before.

| Owner | Player | 2025 status | Old cost (flat model) | **Corrected cost (N-1)** |
|---|---|---|---|---|
| Andrew | Bo Nix | kept at R12 in 2025 | R12 | **R11** |
| Andrew | Jameson Williams | kept at R14 in 2025 | R14 | **R13** |
| Andrew | Kenneth Walker III | drafted 2025 (first keep) | R4 | R4 (unchanged) |
| jomud | Bucky Irving | kept at R12 in 2025 | R12 | **R11** |
| jomud | Chase Brown | kept at R13 in 2025 | R13 | **R12** |
| LoochCarluccio | Bijan Robinson | kept at R2 in 2025 | R2 | **R1 — valid, but his LAST eligible keeper year** |
| pdustin | Jaxon Smith-Njigba | kept at R14 in 2025 | R14 | **R13** |
| PeterCrisileo | Brock Bowers | kept at R8 in 2025 | R8 | **R7** |
| PeterCrisileo | Drake Maye | kept at R13 in 2025 | R13 | **R12** |
| Edeecher | Jahmyr Gibbs | kept at R2 in 2025 | R2 | **R1 — valid, but his LAST eligible keeper year** |
| Edeecher | Jayden Daniels | kept at R5 in 2025 | R5 | **R4** |
| DannyBC1 | Amon-Ra St. Brown | kept at R2 in 2025 | R2 | **R1 — valid, but his LAST eligible keeper year** |
| DannyBC1 | Trey McBride | kept at R6 in 2025 | R6 | **R5** |
| DannyBC1 | Kyren Williams | kept at R3 in 2025 | R3 | **R2** |

All other 15 keepers (Andrew's Walker, tlekes' 2, havicht's 3, jomud's Dak Prescott, LoochCarluccio's
Caleb Williams and Jaxson Dart, pdustin's Kyle Pitts and Blake Corum, PeterCrisileo's Luther Burden,
Edeecher's Emeka Egbuka, jpalmeri1616's 3) were drafted fresh in 2025 — first-time keeps, cost
unchanged from what's already documented everywhere else.

## Keeper equity — the biggest non-obvious edge in this league

The 12th-round rule means **every in-season waiver add carries a hidden second value**: not just what
he does for you in Week 9, but whether he projects as a next-year keeper at a twelfth-round price.

A breakout rookie RB claimed in Week 7 who finishes as an RB2 is an enormous asset — kept next year
for a twelfth. Identical production from a veteran drafted in the third round is keepable only at
third-round cost. Same points, wildly different franchise value.

So:

1. **Every waiver recommendation carries a keeper-equity flag alongside its win-now value.** Two
   players with the same rest-of-season projection are not equal if one is 23 and ascending.
2. **Every drop candidate is ranked with keeper equity accounted for** — dropping a cheap 12th-round
   keeper to stream a defence is usually wrong.
3. **Late-season, once playoff fate is largely settled, defaults flip hard** toward stashing
   ascending young players over marginal veteran upgrades.
4. The `keeper_equity` list in the state file is maintained **all year**, so Week 16 hands Andrew a
   ranked board instead of a reconstruction project in August.
5. Track the **3-consecutive-year cap** so players about to age out are known in advance, not
   discovered at the deadline.

`system/analysis/keeper_equity.py` makes this deterministic. It measures surplus in **rounds, not
points**, because rounds are the currency the rule is written in:

```
surplus_rounds = keeper_cost_round - market_round
```

where `market_round` is where the player would actually go in next year's draft. Bo Nix at a 12th
when a QB of his projection goes in round 5 is +7 rounds of surplus. The module enforces the
eligibility rules (max 3, no 1st-rounders, kept-round carries forward, 3-consecutive-year cap), so
do not hand-roll the arithmetic.

Shape of an entry:

```json
{ "player": "...", "acquired": "waiver_week_5", "keeper_cost_2027": "R12",
  "projected_value": "RB2", "surplus": "very high", "consecutive_years": 1,
  "final_eligible_year": 2029 }
```

## Andrew's 2026 board — FINAL, locked, corrected N-1 costs

Superseded history (leaning plan, then "locked but flat-cost", then the N-1 correction) collapsed
here — see git/file history if the intermediate steps matter. This is the current, applied state.

**Andrew's locked keepers (confirmed live in Sleeper, deadline passed 2026-08-23):**

| Keep | Cost | Forfeits (overall pick) | Consecutive yrs | Final eligible year |
|---|---|---|---|---|
| Kenneth Walker III | R4 | 33 | 1 | 2028 (first-time keep, unaffected by N-1) |
| Bo Nix | **R11** (was R12, N-1 applied) | **108** (was 113) | 2 | **2026 is his last flat year — R10 next if kept again in 2027** |
| Jameson Williams | **R13** (was R14, N-1 applied) | **128** (was 133) | 2 | same — **R12 next if kept in 2027** |

Passed over: **Puka Nacua (R2)** — ranked #2, but replaceable with the R1 pick (London/Lamb tier).
**Mike Evans (R4)** — ranked #3; age 33, new team/QB/scheme at once, and a TD-dependent profile that
fits a first-down-bonus format poorly.

The reasoning that decided it: true workhorse RBs are the league's scarcest commodity, while an
elite WR can be approximated with Andrew's own Round 1 pick.

## League-wide keeper lock status — FINAL, all 10 teams confirmed 2026-08-24

All 10 teams locked (deadline Sun Aug 23, 8pm ET, confirmed passed). Full board with corrected N-1
costs in the table above (`## Full 2026 keeper board`). Three players league-wide (Gibbs, Bijan
Robinson, Amon-Ra St. Brown) are in their final eligible keeper year at R1 — see the resolved note at
the top of this file.

Draft confirmed live via `draft_id` `1389753893356838913`: **Monday, Aug 24, 2026, 8:00pm ET**
(`start_time` epoch `1787616007000`) — today, not the earlier "Aug 28" placeholder. `draft_order` is
still `null` in Sleeper's own field (showing default identity mapping) — this does not contradict the
owner-supplied slot order in `league_reference.md` §8, the commissioner just hasn't entered it into
Sleeper's draft board yet.

## Draft-pick consequences (slot 8, 2026) — FINAL

Andrew forfeits overall picks **33 (Kenneth Walker III, R4), 108 (Bo Nix, R11), and 128 (Jameson
Williams, R13)** — note 108 and 128 are NEW forfeiture points (previously 113 and 133 under the flat
cost model); picks 113 and 133 are now LIVE for Andrew instead. See `league_reference.md` §8 for the
full corrected gap/risk table — the biggest finding there: **picks 73→88 is now a fully live,
zero-pre-known 14-pick stretch**, the single highest-risk gap on the entire board.

## POST-DRAFT (2026-08-25): actual results

The draft completed the night of 2026-08-24 (15 rounds, not 16 — resolves the bench-count open flag
that was live in `draft_board_2026.md` at deadline: 9 starters + 6 bench = 15, clean). Kenneth Walker
III, Bo Nix, and Jameson Williams all auto-filled at their forfeited picks (33, 108, 128) exactly as
modeled here. Full post-draft team-by-team report and league power ranking: `draft_report_2026.md`.

## Recomputing costs after the 2026 draft

Fetch `/v1/draft/1389753893356838913/picks` (now complete — 150 picks, 15 rounds) and save as
`raw/draft_2026_picks.jsonl`, then ingest. That reseeds the player cache with current-season teams and
establishes every player's 2027 keeper cost (this year's draft round, or N-1 off this year's keeper
cost for anyone kept again) in one call.
