# Keeper rules and keeper equity

## The rules (as written by the commissioner)

- Keep up to **3 players**.
- Cost to keep = **the round the player was drafted last year**, or the round he was **kept at** last
  year — that round carries forward.
- **1st-round picks are not keeper-eligible.**
- A player added off **waivers or free agency who was never drafted costs a 12th-round pick**.
- **No player may be kept more than 3 consecutive years.**
- Keeping a player forfeits that round's pick in the coming draft.
- Draft-pick trading is allowed, which interacts with all of the above.
- **UNVERIFIED:** the lock deadline. Sleeper carries `keeper_deadline: "1"` with no readable date —
  confirm with tlekes.

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

## Andrew's 2026 board

Keeper cost = round drafted/kept in 2025. Players not in the 2025 draft are FA adds at R12.

| Player | Pos | Cost | Note |
|---|---|---|---|
| Puka Nacua | WR | R2 | kept '25 |
| Kenneth Walker | RB | R4 | now KC, Super Bowl LX MVP |
| Mike Evans | WR | R4 | now **SF**, not TB |
| Tetairoa McMillan | WR | R5 | |
| DeVonta Smith | WR | R6 | |
| Travis Kelce | TE | R7 | confirmed returning, KC TE1 |
| Joe Mixon | RB | R8 | unsigned, chronic foot issue — effectively unrosterable |
| Jordan Mason | RB | R10 | |
| Bo Nix | QB | R12 | kept '25 |
| Javonte Williams | RB | R13 | |
| Jameson Williams | WR | R14 | kept '25 |
| Ashton Jeanty | RB | — | 2025 R1 — **not eligible** |
| bench/depth adds | — | R12 | never drafted |

**Plan as of 2026-08-07 (leaning, not locked — `rosters[2].keepers` is still null):**

| Keep | Cost | Forfeits | Consecutive yrs | Final eligible year |
|---|---|---|---|---|
| Kenneth Walker III | R4 | overall pick 33 | 1 | 2028 |
| Bo Nix | R12 | overall pick 113 | 2 | **2027** |
| Jameson Williams | R14 | overall pick 133 | 2 | **2027** |

Passed over: **Puka Nacua (R2)** — ranked #2, but replaceable with the R1 pick (London/Lamb tier).
**Mike Evans (R4)** — ranked #3; age 33, new team/QB/scheme at once, and a TD-dependent profile that
fits a first-down-bonus format poorly.

The reasoning that decided it: true workhorse RBs are the league's scarcest commodity, while an
elite WR can be approximated with Andrew's own Round 1 pick. Nix and Jameson both hit their **final
eligible year in 2027** if kept again — flag that before the 2027 board is built.

## Draft-pick consequences (slot 8, 2026)

R4 (p33), R12 (p113) and R14 (p133) are forfeited to the three keeps. That creates a 19-pick dead
zone between p28 and p48, and two more late (108→128, 128→148). **Anything Andrew needs must be
secured before a dead zone, never planned for after one.**

## Recomputing costs after the 2026 draft

Fetch `/v1/draft/1389753893356838913/picks` **once**, right after Aug 28, save as
`raw/draft_2026_picks.jsonl`, and ingest. That reseeds the player cache with current-season teams and
establishes every player's 2027 keeper cost in one call. It is the single highest-value one-time
fetch in the system.
