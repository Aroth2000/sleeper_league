# Sunday Scaries Keeper League — Reference Doc

**Platform:** Sleeper | **League ID:** `1389753893356838912` | **Season:** 2026 (Year 3 of the league)
**Data pulled:** August 5, 2026, via Sleeper's public read-only API (no login needed — just the league ID above; endpoints listed at the bottom if this needs refreshing later).

---

## 1. Season timeline (so nobody gets confused by "Season 2" language)

- **Year 1 (2024 season):** original league, previous keeper/flex setup (2 flex spots, per the "Season 2 Changes" doc referencing what changed *away from*).
- **Year 2 (2025 season):** commissioner's "Season 2 Changes" took effect — flex dropped from 2 spots to 1, waivers were still rolling. Confirmed in Sleeper's actual 2025 draft settings (`slots_flex: 1`, `slots_super_flex: 1`, 7 bench spots).
- **Year 3 (2026 season — the upcoming draft):** this is what we're prepping for. **Important:** Sleeper's live 2026 draft settings currently show `slots_flex: 2` again (back up from 1) with bench trimmed to 6. That's *different* from both the "Season 2 Changes" doc and last year's actual settings, and nothing in writing says flex was bumped back up for Year 3. **Confirm with the commissioner before draft day** — it meaningfully changes positional value (more flex = more demand for RB/WR/TE depth).

---

## 2. Core league settings (2026, as configured in Sleeper)

- 10 teams, Superflex (`scoring_type: 2qb`)
- Draft: **Wednesday Aug 28, 2026, 7:30pm ET**, snake, randomized order released at 6:30pm
- Draft length: 16 rounds
- Roster (per current Sleeper settings): **QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX, DEF** starting (10 starters), **6 bench**
- Playoffs: top 6 teams, playoffs start week 15
- Trade deadline: week 13
- Draft pick trading: **allowed**
- Waivers (Season 3 change): **reverse-standings rolling** (worst record gets first priority each week, replacing the old rolling-waivers system)
- DEF scoring: known to be **overpowered/buggy** last year — commissioner flagged "Fix Def scoring (TBD)" for this season. Don't trust old DEF fantasy totals until this is confirmed fixed.

---

## 3. Scoring (half-PPR + half-point-per-first-down)

Full-point/notable settings pulled directly from Sleeper:

| Category | Value |
|---|---|
| Reception | 0.5 |
| Reception first down | 0.5 |
| Rush first down | 0.5 |
| Pass yard | 0.04 (25 yds = 1 pt) |
| Rush/Rec yard | 0.1 (10 yds = 1 pt) |
| Pass TD | 4 |
| Rush/Rec TD | 6 |
| Pass INT (thrown) | -1 |
| Fumble lost | -2 |
| 2pt conversion (any) | 2 |
| Sack (IDP-style, def) | 1 |
| Def INT | 2 |
| Def fumble recovery | 2 |
| Def/ST TD | 6 |
| Points allowed 0 | 10 |
| Points allowed 1–6 | 7 |
| Points allowed 7–13 | 4 |
| Points allowed 14–20 | 1 |
| Points allowed 21–27 | 0 |
| Points allowed 28–34 | -1 |
| Points allowed 35+ | -4 |

**Strategic read:** the 0.5-per-first-down bonus quietly rewards possession/chain-moving players (slot receivers, check-down backs, possession TEs) over pure boom-or-bust deep threats. Worth nudging those player types up your personal rankings relative to standard half-PPR ADP.

---

## 4. Keeper rules (as written by the commissioner)

- Keep up to **3 players**
- Cost to keep a player = **the round they were drafted (or kept) the previous year**
- **Cannot keep 1st-round picks**
- Keeping a player originally added as a **free agent/waiver pickup** (never drafted) costs a **12th-round pick**
- **Cannot keep the same player more than 3 consecutive years**
- Draft pick trading is allowed, which interacts with keepers (see strategy notes)

---

## 5. Team directory

| Team | Owner (Sleeper handle) | User ID |
|---|---|---|
| Pabst Interference | tlekes (commissioner) | 1123669553063526400 |
| **Andrew's team** | andrewroth32 | 1128203360286429184 |
| Water, Barkley, and Hops | havicht | 1128898667324239872 |
| (no team name set) | jomud | 1129508145568686080 |
| Glizzy Guzzler | LoochCarluccio | 603841382339108864 |
| Mass General Hospital | pdustin | 869724998703763456 |
| Still at RPI | PeterCrisileo | 870744736284196864 |
| Ethan's Younglings | Edeecher | 869654771978641408 |
| (no team name set) | DannyBC1 | 1131700966283177984 |
| Big Mommy Milkers (UCSF) | jpalmeri1616 | 1133830654808072192 |

---

## 6. 2026 keeper-cost board (every rostered player, computed from the actual 2025 draft)

Cost = round they were drafted in 2025, OR the round they were *kept at* in 2025 if they were already a keeper last year (marked "kept '25" below) — that round carries forward as this year's cost. Players not found in the 2025 draft are FA/rookie adds and would cost a 12th-round pick to keep. 1st-round players are **not keeper-eligible**.

### Andrew's team (andrewroth32)
| Player | Pos | 2026 keeper cost | Note |
|---|---|---|---|
| Puka Nacua | WR | R2 | kept '25 (2nd consecutive year if kept again) |
| Kenneth Walker | RB | R4 | |
| Mike Evans | WR | R4 | **now on San Francisco 49ers (signed FA, 3yr/$42M) — no longer Tampa Bay**, see Section 13 |
| Tetairoa McMillan | WR | R5 | |
| DeVonta Smith | WR | R6 | |
| Travis Kelce | TE | R7 | |
| Joe Mixon | RB | R8 | **effectively unrosterable — unsigned, chronic foot/circulation issue, has told friends he believes his career is over; see Section 13** |
| Jordan Mason | RB | R10 | |
| Bo Nix | QB | R12 | kept '25 (2nd consecutive year if kept again) |
| Javonte Williams | RB | R13 | |
| Jameson Williams | WR | R14 | kept '25 (2nd consecutive year if kept again) |
| Ashton Jeanty | RB | **N/A** | 1st-round pick — not keeper eligible |
| 4 unnamed bench/depth pieces | — | R12 (FA cost) | never drafted in 2025 |

**Working take (updated Aug 7, 2026 after full research — see Section 13 for complete reasoning):** Jameson Williams (R14, confirmed entrenched Detroit WR2) and Bo Nix (R12, confirmed healthy unquestioned starter) are clear surplus-value keeps. The 3rd slot is now a genuine 3-way call — Puka Nacua (R2) vs. Kenneth Walker III (R4, confirmed unchallenged Chiefs workhorse) vs. Mike Evans (R4, now SF's new WR1) — and the verdict is **keep Walker**: true workhorse RBs are the league's scarcest commodity right now, while an elite WR (Puka-tier) can be approximated with Andrew's own Round 1 pick (Drake London/CeeDee Lamb are both there). Evans is a good value at R4 but not good enough to leapfrog Walker or Puka given his age, team/scheme change, and TD-dependent profile fitting this scoring format worse. Also: if Nix/Jameson are kept again this year, 2027 would be their final eligible year under the 3-consecutive-year cap.

### League-wide keeper landscape (other teams, for context on what's likely off the board)
- **Glizzy Guzzler (LoochCarluccio) — already locked on Sleeper:** Bijan Robinson (R2), Caleb Williams (R4), Jaxson Dart (R13, rookie QB — cheap superflex depth play)
- **Water, Barkley, and Hops (havicht):** cheap value on Saquon Barkley (R3, kept '25), Josh Jacobs (R5, kept '25), David Montgomery (R9, kept '25)
- **jomud:** Nico Collins (R5, kept '25), Bucky Irving (R12, kept '25), Chase Brown (R13, kept '25) — lots of cheap RB/WR value
- **Mass General Hospital (pdustin):** Justin Jefferson (R2, kept '25), Derrick Henry (R4, kept '25), Jaxon Smith-Njigba (R14, kept '25)
- **Still at RPI (PeterCrisileo):** Brock Bowers (R8, kept '25), Ladd McConkey (R10, kept '25), Drake Maye (R13, kept '25)
- **Ethan's Younglings (Edeecher):** Jahmyr Gibbs (R2, kept '25), De'Von Achane (R4, kept '25), Jayden Daniels (R5, kept '25)
- **DannyBC1:** Amon-Ra St. Brown (R2, kept '25), Kyren Williams (R3, kept '25), Trey McBride (R6, kept '25)
- **Big Mommy Milkers (jpalmeri1616):** George Kittle (R8, kept '25), Terry McLaurin (R9, kept '25)
- **Pabst Interference (tlekes, commissioner):** A.J. Brown (R2, kept '25) is the standout cheap keep

Only Glizzy Guzzler had locked their keepers in Sleeper as of this pull (Aug 5) — everyone else's `keepers` field was still empty, so the above for other teams is "likely candidates based on cost/value," not confirmed picks.

---

## 7. Draft strategy takeaways (full discussion from Aug 5, 2026)

- QB is a land grab in this superflex format — 15-18 QBs will be needed leaguewide once backups are counted, so don't wait on QB2 the way you would in a 1-QB league.
- The double-flex setup (2 FLEX + 1 SUPERFLEX, *if* that setting holds — see the Section 1 flag) makes RB/WR/TE depth matter more than standard formats.
- Half-point-per-first-down favors possession/chain-moving players over pure deep threats — nudge personal rankings accordingly.
- Only 6 bench spots this year (down from 7) — less room to stash handcuffs/speculative rookies than in past years.
- Up to 30 draft picks leaguewide could disappear into keeper slots — expect real gaps in the live draft board relative to ADP, especially rounds 2-14 given how many cheap keepers are floating around (see Section 6).
- Draft pick trading is allowed — a good lever if you'd rather cash in a keeper-eligible player's draft slot for extra picks from a team that gutted its draft with keepers.
- Reverse-standings waivers reward patience — a rough start actually improves waiver priority rather than hurting it, so leaning bench-heavy at RB (highest injury churn) is reasonable.
- Don't trust old DEF fantasy scoring — the scoring bug is being fixed; treat DEF as a late-round dart throw.

---

## 8. LIVE TRACKER: draft slot selection (update as it happens)

**✅ FULL DRAFT ORDER CONFIRMED (Aug 11, 2026) — reported directly by Andrew from the actual league draft order, not derived from our reverse-PF prediction model.** This supersedes the predicted table below entirely.

| Slot | Owner (real name) | Sleeper handle | Team name |
|---|---|---|---|
| 1 | Peter Dustin | pdustin | Mass General Hospital |
| 2 | Grady Habicht | havicht | Water, Barkley, and Hops |
| 3 | Toluwaleke Semowo | tlekes | Pabst Interference (commissioner) |
| 4 | Jack Palmeri | jpalmeri1616 | Big Mommy Milkers (UCSF) |
| 5 | Peter Crisileo | PeterCrisileo | Still at RPI |
| 6 | Danny Bierman Chow | DannyBC1 | (team name not yet on file) |
| 7 | Ethan Deecher | Edeecher | Ethan's Younglings |
| 8 | **Andrew Roth** | **andrewroth32** | **(Andrew — CONFIRMED slot 8, consistent with earlier independent confirmation)** |
| 9 | Matthew Carluccio | LoochCarluccio | Glizzy Guzzler |
| 10 | Jonah Mudse | jomud | (team name not yet on file) |

Consistency check against prior data: slot 1 = pdustin, slot 2 = havicht, and slot 8 = Andrew were all independently confirmed earlier in this project and match this list exactly. High confidence this mapping is correct.

**✅ RESOLVED (Aug 12, 2026):** the full 16-round snake pick order has now been computed from the confirmed slot table above and cross-checked pick-for-pick against the "Slot 8 pick map" below (all 16 of Andrew's overall-pick numbers — 8, 13, 28, 33, 48, 53, 68, 73, 88, 93, 108, 113, 128, 133, 148, 153 — reproduce exactly). This resolved order is now used in `draft_board_2026.md`, section **"0. THE SEAT MAP"** (opponent-seat modeling, rival draft-day holes, who picks immediately before/after Andrew, and the mock-draft trees). Andrew's neighbors are constant across every one of his 13 live picks, since slot 8 sits mid-pack and is never at a snake turn boundary: **Ethan Deecher (Edeecher, slot 7)** always picks immediately before or after him, and **Matthew Carluccio (LoochCarluccio, slot 9)** always picks on the other side (which side is "before" vs. "after" alternates each round with the snake direction). The superseded predicted table below is kept for audit trail only.

<details>
<summary>Superseded: predicted order used before Aug 11, 2026 (kept for reference/audit trail only)</summary>

| Selection order (predicted) | Team (predicted) | Slot claimed | Status |
|---|---|---|---|
| 1st | Mass General Hospital (pdustin) | Slot 1 | ✅ confirmed — matches actual |
| 2nd | Water, Barkley, and Hops (havicht) | Slot 2 | ✅ confirmed — matches actual |
| 3rd | Pabst Interference (tlekes) | ? | actual: Slot 3 — matches |
| 4th | Big Mommy Milkers (jpalmeri1616) | ? | actual: Slot 4 — matches |
| 5th | jomud | ? | actual: jomud is Slot 10, not 5th — guess was wrong |
| 6th | Glizzy Guzzler (LoochCarluccio) | ? | actual: LoochCarluccio is Slot 9, not 6th — guess was wrong |
| 7th | **Andrew** | **Slot 8** | ✅ CONFIRMED — Andrew took slot 8 |
| 8th | Still at RPI (PeterCrisileo) | ? | actual: PeterCrisileo is Slot 5, not 8th — guess was wrong |
| 9th | DannyBC1 | ? | actual: DannyBC1 is Slot 6, not 9th — guess was wrong |
| 10th | Ethan's Younglings (Edeecher) | ? | actual: Edeecher is Slot 7, not 10th — guess was wrong |

</details>

**RESOLVED: Andrew is drafting from SLOT 8** — the third-best outcome on our preference ranking (10 > 9 > 8 > 7 > ...), and squarely in the preferred late-slot band. Rationale for that ranking: with a lot of round-2-through-9 talent kept off the board, the post-round-1 cliff is unusually steep, so getting your second pick quickly matters more than usual.

**Slot 8 pick map (160 total picks; keepers consume the pick in their cost round):**

| Round | Overall pick | Status |
|---|---|---|
| R1 | 8 | live |
| R2 | 13 | live |
| R3 | 28 | live |
| R4 | 33 | **forfeited — Kenneth Walker keep** |
| R5 | 48 | live |
| R6 | 53 | live |
| R7 | 68 | live |
| R8 | 73 | live |
| R9 | 88 | live |
| R10 | 93 | live |
| R11 | 108 | live |
| R12 | 113 | **forfeited — Bo Nix keep** |
| R13 | 128 | live |
| R14 | 133 | **forfeited — Jameson Williams keep** |
| R15 | 148 | live |
| R16 | 153 | live |

13 live picks + 3 keepers = 16 roster spots. **Pick rhythm matters enormously here:** picks 8 and 13 are only 4 apart (the slot-8 turn — two premium players in quick succession). Then there is a **19-pick dead zone between p28 and p48** caused by forfeiting R4 to the Walker keep. Mid-draft settles into turn-adjacent pairs (48/53, 68/73, 88/93) separated by 14-pick waits. Two more 19-pick dead zones hit late (108→128 and 128→148) from the R12/R14 forfeits. Anything Andrew needs must be secured *before* a dead zone, never planned for after one.

**Roster needs after keepers:** QB2 (for SUPER_FLEX), RB2, WR2, TE, 2x FLEX, DEF, plus 6 bench. Note he currently has **no tight end**, and only one RB and one WR.

---

## 9. LIVE TRACKER: keeper decisions by team

| Team | Keepers | Status |
|---|---|---|
| Glizzy Guzzler (LoochCarluccio) | Bijan Robinson (R2), Caleb Williams (R4), Jaxson Dart (R13) | ✅ locked on Sleeper |
| Andrew | Updated lean (Aug 6 full sweep): Kenneth Walker III (R4) + Bo Nix (R12) + Jameson Williams (R14, re-verify status) — Puka Nacua (R2) dropped from the plan; see Section 13 | decision pending, leaning toward this trio |
| Water, Barkley, and Hops (havicht) | unconfirmed — likely candidates: Saquon Barkley (R3), Josh Jacobs (R5), David Montgomery (R9) | unconfirmed |
| jomud | unconfirmed — likely candidates: Nico Collins (R5), Bucky Irving (R12), Chase Brown (R13) | unconfirmed |
| Mass General Hospital (pdustin) | unconfirmed — likely candidates: Justin Jefferson (R2), Derrick Henry (R4), Jaxon Smith-Njigba (R14) | unconfirmed |
| Still at RPI (PeterCrisileo) | unconfirmed — likely candidates: Brock Bowers (R8), Ladd McConkey (R10), Drake Maye (R13) | unconfirmed |
| Ethan's Younglings (Edeecher) | unconfirmed — likely candidates: Jahmyr Gibbs (R2), De'Von Achane (R4), Jayden Daniels (R5) | unconfirmed |
| DannyBC1 | unconfirmed — likely candidates: Amon-Ra St. Brown (R2), Kyren Williams (R3), Trey McBride (R6) | unconfirmed |
| Big Mommy Milkers (jpalmeri1616) | unconfirmed — likely candidates: George Kittle (R8), Terry McLaurin (R9) | unconfirmed |
| Pabst Interference (tlekes) | unconfirmed — likely candidate: A.J. Brown (R2) | unconfirmed |

Update this table whenever Andrew reports a new lock-in or the Sleeper `keepers` field changes.

---

## 10. LIVE TRACKER: players confirmed falling back into the draft pool

Once a team locks keepers, every other player on their roster (that isn't a DEF) returns to the live draft pool for anyone to take. Confirmed so far:

**From Glizzy Guzzler (kept Bijan Robinson, Caleb Williams, Jaxson Dart):** Breece Hall (RB), Jordan Love (QB), Malik Nabers (WR), Tyler Warren (TE), Quinshon Judkins (RB), Chris Olave (WR), CeeDee Lamb (WR — was already ineligible as a 2025 R1 pick regardless), Brian Thomas (WR), plus a few unidentified bench pieces.

All other teams' rosters are still fully "in doubt" pending their keeper locks — once those come in, use Section 6's per-team cost table to know exactly what falls back.

---

## 11. Player value alert — directly affects Andrew's keeper decision

**Kenneth Walker III (on Andrew's roster, 2026 keeper cost R4) signed with the Kansas City Chiefs in free agency after being named Super Bowl LX MVP.** Multiple outlets (ESPN, NFL.com, Fox Sports) report he got one of the largest RB contracts in league history and is expected to see "the largest workload of his career" behind Kansas City's line, playing alongside Patrick Mahomes — a major offensive upgrade from splitting Seattle's backfield with Zach Charbonnet. This substantially raises his redraft/keeper value.

**Practical effect:** this reshuffles Andrew's 3rd-keeper decision. Walker at an R4 cost now looks like excellent surplus value alongside the Jameson Williams (R14) and Bo Nix (R12) locks discussed earlier — arguably a stronger case than Puka Nacua at R2, since Puka's cost already tracks close to his real value while Walker's has jumped well past his R4 price tag.

Side effect worth knowing: Seattle's backfield opened up because Walker left — see rookie Jadarian Price in Section 12, who directly benefits.

---

## 12. 2026 rookie class — names worth knowing for the live draft (pulled Aug 5, 2026)

Sourced from CBS Sports, Fox Sports, and other fantasy outlets' rookie rankings. These are real draft-day considerations, not just waiver stashes, since this is a full redraft.

**Running backs**
- Jeremiyah Love (ARI, 3rd overall) — the headline rookie RB, 3-down profile, but stuck on a weak Arizona team.
- Jadarian Price (SEA, 32nd overall) — benefits directly from Kenneth Walker's departure (see Section 11) and Zach Charbonnet's injury recovery; one of the best pure opportunity spots of any rookie.
- Kaelon Black (SF, 3rd round) — CMC's backup; boom potential only on injury.
- Nicholas Singleton (TEN), Jonah Coleman (DEN), Kaytron Allen (WAS) — depth-chart dependent, monitor camp/preseason news.

**Wide receivers**
- Carnell Tate (TEN, 4th overall) — Titans' No. 2 WR opposite Chris Olave; upside tied to Cam Ward's development.
- Jordyn Tyson (NO, 8th overall) — complements Chris Olave in New Orleans, should see volume as defenses key on Olave.
- Kaelon Boston (CLE, 39th overall) — big-bodied (6'4"/212) target in a Browns WR room with no proven touchdown scorer.
- Makai Lemon (PHI), KC Concepcion (CLE), Omar Cooper Jr. (NYJ) — depth WR3/4 dynasty-flavored options, lower near-term redraft priority.

**Tight ends**
- Kenyon Sadiq (NYJ) — clearest immediate-opportunity rookie TE, Jets' TE room was unproductive last year.
- Eli Stowers (PHI) — could carve into Dallas Goedert's role/red-zone work.
- Justin Joly (DEN), Max Klare (LAR) — long-term stashes, murkier 2026 paths.

**Quarterbacks** (lower redraft urgency in a 10-team superflex unless a starting job opens)
- Fernando Mendoza (LV) — buried behind Kirk Cousins for now, dynasty-only.
- Ty Simpson (LAR), Carson Beck (ARI) — monitor camp battles.

---

## 13. News sweep — COMPLETE + gap-filled (Aug 6-7, 2026)

The full 58-agent research sweep finished (all 32 NFL teams, all 11 of Andrew's keeper-eligible players individually, ~25 other-teams'-likely-keepers, and the trade/handcuff/rookie/QB-battle themes). A follow-up audit then found that 5 "incomplete" player entries were actually already answered by the team-sweep data (just never cross-referenced), and one real gap (Joe Mixon) got a fresh, conclusive research pass. The roster section and this recommendation were both rewritten with the corrections. **Full findings for every section — including the corrected roster writeup — live in the companion file `news_sweep_full_report.md`.** See `gap_fill_plan.md` for the full audit trail. What follows is the final, corrected recommendation.

**Headline corrections from the gap-fill pass:** Mike Evans signed with the **San Francisco 49ers** as their new WR1 (3yr/$42M) — he's no longer a Buccaneer, and this turned the 3rd-keeper decision into a genuine 3-way race. Travis Kelce is **confirmed returning for a 14th season** as Kansas City's unchallenged TE1 — the earlier "retirement risk" flag is resolved. Joe Mixon is **unsigned with no known suitor**, has a chronic, unresolved foot/circulation issue, hasn't played since January 2025, and has reportedly told friends he believes his career is over — treat him as effectively unrosterable.

### 1. Draft slot preference — theory holds, still unchanged by this round of corrections

**Final ranking: 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2 > 1 — unchanged.**

The mechanism is still "how much value decays between your Round 1 pick and your Round 2 pick," and none of this update's corrections touch that mechanism:

- **Round 1 stays uniformly elite regardless of slot.** The 10 repatriated 2025-first-rounders (Chase, Allen, Lamar, Burrow, CMC, Jeanty, Jonathan Taylor, Hurts, London, Lamb) are all clean-to-positive. Nothing in the corrected roster section — Evans' team change, Kelce's return, Mixon's non-status — touches this tier. Picking 10th still nets a legitimate stud.
- **The Round 2 cliff is still confirmed deeper than assumed.** Gibbs, Bijan, Henry, Chase Brown, Kyren Williams, JSN, Nico Collins, McLaurin, Bowers, Maye, Caleb Williams are all locked-in keepers elsewhere. That pool stays thin regardless of what's happening on Andrew's own roster.
- **Andrew still has zero need to fight for an early QB.** Bo Nix remains a cheap, healthy-trending, uncontested-starter keeper, so the one argument for an early slot (guaranteeing a top-3 superflex QB) still doesn't apply to him.
- **Soft offset, now partly resolved:** A.J. Brown's "might get cut loose in New England" risk is unchanged (he was in fact traded away, and Philadelphia's WR1 job simply passed to DeVonta Smith rather than to Brown having a resurgence). Josh Jacobs and George Kittle risk is unchanged. None of this moves the needle on Andrew's own slot logic — it's still a "the later I go, the more free information and surprise value I capture" argument.

**Bottom line: nothing in the corrected roster report changes the slot math.** Take the highest number available when Andrew's turn comes.

### 2. 3rd keeper decision — now a genuine 3-way race (Puka R2 vs. Walker R4 vs. Evans R4), but the verdict still lands on Walker

This is the section that actually changes shape. Mike Evans signing with San Francisco as their new WR1 turns what was a clean 2-horse race into a real 3-way comparison, because Evans now sits at the exact same keeper cost (4th round) as Kenneth Walker III.

**The three options, head to head:**

- **Puka Nacua (2nd round):** Reaffirmed top-5-overall asset — 2025 overall WR1 (129/1,715/10), First-Team All-Pro, fully healthy, zero holdout risk, exclusively first-team reps in camp. Elite, but the most expensive of the three.
- **Kenneth Walker III (4th round):** Unchallenged KC lead back on a fresh 3-year/$45M deal, with Pacheco and Hunt both gone and only a 5th-round rookie behind him. Glowing Andy Reid praise, expected expanded passing role in a top-tier offense. Cheapest elite-tier RB option in the league.
- **Mike Evans (4th round):** New 3-year/$42M deal, now San Francisco's clean WR1 in Brock Purdy's offense, with an injured RB corps and a Kittle-on-PUP situation that could funnel extra red-zone/early-down passing volume his way. But he's turning 33 this month, changing teams, QBs, and schemes simultaneously, and his contested-catch/TD-dependent profile is a middling fit for a first-down-bonus format that rewards high-target-share possession receivers more than boom-bust scorers.

**Why Walker still wins, even against a same-priced competitor now:**

Comparing Walker and Evans directly at equal cost (4th round each), Walker is the clearly stronger hold: he's an established, proven every-down producer (Super Bowl LX MVP) stepping into a completely open depth chart in a historically efficient offense, versus Evans, who is a 33-year-old receiver adjusting to a new team, new quarterback, and new scheme all at once, in a scoring format that already discounts his TD-dependent style. Evans is a good buy, not a great one, at this format and price.

That leaves the same comparison as before between Walker and Puka: true workhorse RBs are the scarce league-wide commodity (nearly every other backfield in the league is a stated committee), while elite bell-cow-caliber WRs remain available as *draft* replacements — Drake London or CeeDee Lamb sit right there in Round 1 as near-equivalent fallback studs if Andrew lets Puka go. There's no equivalent Round 1 fallback for a true workhorse RB beyond Jonathan Taylor/CMC, and Andrew only gets one Round 1 pick regardless.

**Final verdict: keep Kenneth Walker III as the 3rd keeper.** Puka Nacua is the correct #2 in this ranking (excellent value, but you can approximate his output with a Round 1 WR pick). Mike Evans is the correct #3 — a legitimately good value at a 4th-round cost, but not good enough to leapfrog either Walker or Puka once you weigh scarcity, format fit, and adjustment risk. If keeper rules allow only the top slot to be locked, both Puka and Evans go back into the shared draft pool — worth flagging to Andrew that if either slips, they're strong value grabs at market price rather than at keeper price.

**Other roster notes relevant to this decision:**

- **Jameson Williams** — no longer a research gap. Confirmed entrenched as Detroit's WR2 with a stable role and no camp competition. His 14th-round keeper cost is cheap enough that this was always low-risk, and now it's fully de-risked; keep him without hesitation.
- **Travis Kelce** — the retirement/roster uncertainty is resolved, not an open flag anymore. He's confirmed returning for a 14th season as Kansas City's clear, unchallenged TE1 (GM Brett Veach: "not going out like this"). Treat him as a normal aging-curve TE1 asset now — no more urgency, no contingency plan needed. The only real watch item going forward is ordinary age-decline (turns 37 in October, target share already trending down since 2023) plus Mahomes' recovery timeline, not any retirement/roster risk.
- **Joe Mixon** — downgraded further, not just "unresolved." He remains unsigned, has a chronic, poorly-resolved foot/blood-flow condition, hasn't played since January 2025, and has reportedly told friends he believes his career is over. Treat him as effectively unrosterable — don't spend a bench spot or draft-day thought on him. A quick pre-draft check is cheap insurance, but no signing or return is currently expected.

### 3. Prioritized action list for Aug 28 draft day

1. **Slot claim:** When it's Andrew's turn (7th), take the latest-numbered slot still available — prefer 10, then 9, 8, 7… in that order.
2. **Keeper lock:** Finalize Kenneth Walker III as keeper #3 over both Puka Nacua and the newly relevant Mike Evans, given his confirmed unchallenged workhorse role and cheap 4th-round cost. Jameson Williams (14th round) is a confirmed, low-risk keep. If the format allows re-drafting non-kept players, watch for Puka or Evans slipping — both are strong value if available at market price.
3. **Round 1 target list (in rough order of fit):** Jonathan Taylor or CMC (if Andrew wants a true workhorse RB1 to pair with Walker) — otherwise Drake London or CeeDee Lamb (elite WR to cover the Puka-replacement need). Don't reach for Allen/Lamar/Burrow — Bo Nix already covers the superflex slot.
4. **Cross off the board — these will NOT be available:** Jahmyr Gibbs, Bijan Robinson, Derrick Henry, Chase Brown, Kyren Williams, Jaxon Smith-Njigba, Nico Collins, Terry McLaurin, Brock Bowers, Drake Maye, Caleb Williams — all now near-lock keepers elsewhere, don't plan around getting them.
5. **Watch for buy-low slippage from shaky/relocated players:** A.J. Brown (now on New England after the trade, still carries chemistry/role risk there), Josh Jacobs (domestic-violence arrest risk), George Kittle (Achilles, starting camp on PUP), Brian Thomas Jr. (down 2025 year) — and if Andrew doesn't keep him, Mike Evans himself becomes exactly this kind of buy-low: a 33-year-old, TD-dependent WR adjusting to a new team, worth a discounted price rather than a premium one in this format.
6. **Grab Walker's own insurance:** Emari Demercado (and depth piece Emmett Johnson) as a cheap late-round handcuff to Andrew's own keeper — Walker has essentially zero proven competition, so his backup is a near-free stash.
7. **Target correlated Denver value for Bo Nix:** Jonah Coleman (rookie, praised by Payton, path to short-yardage/passing work) as a cheap piece that could vulture rushing TDs/first-downs from an injury-prone J.K. Dobbins — this directly boosts Nix's ecosystem in a first-down-bonus format.
8. **Best true handcuffs still worth a late pick:** Jordan Mason (MIN) is a proven-producer handcuff to Aaron Jones' recurring hamstring issue and worth holding regardless of keeper status; Isiah Pacheco (DET, elite handcuff to Gibbs), Tank Bigsby (PHI, strong handcuff to Barkley), Ray Davis (BUF, standalone value already). Joe Mixon is not part of this conversation — treat him as off the board entirely.
9. **Seattle backfield dart-throw:** George Holani or Jadarian Price — Walker's gone, Charbonnet is hurt (PUP into October), and this is a wide-open lead-RB job in a contending offense; cheap, high-upside late pick.
10. **TE value plays:** Isaiah Likely (NYG, escaped Andrews' shadow, real starting role) and Harold Fannin Jr. (CLE, proven 72-catch rookie, now clear TE1) — both fit the first-down-bonus/possession-catch profile well. Note Andrew does not need any Kelce-specific contingency plan anymore; his TE1 slot is secure.
11. **Format fit reminder:** in half-PPR + first-down bonus, prioritize high-target-share/possession/chain-moving players (Godwin, Egbuka, Jayden Higgins-type, and on Andrew's own roster, DeVonta Smith and Tetairoa McMillan) over boom-bust vertical or contested-catch/TD-dependent guys — be cautious pricing a player like Mike Evans at a premium given his age, scheme change, and TD-dependent profile.
12. **Post-draft/trade watch:** whoever wins Atlanta's Tua-vs-Penix QB battle and Minnesota's Murray-vs-McCarthy battle becomes a streamable value add given the weapons around each (Bijan/London; Jefferson) — monitor for in-season trade targets, not draft-day picks.

---

## 14. Open questions to confirm with the commissioner before Aug 28

1. Is FLEX really 2 spots for 2026, or should it be 1 (matching the "Season 2 Changes" doc)? Sleeper currently shows 2.
2. Has the DEF scoring fix actually been applied yet?
3. Keeper decision deadline — Sleeper metadata shows a `keeper_deadline` flag but not a clear date/time.

---

## 15. How this was compiled (for refreshing later)

Pulled via Sleeper's free, no-auth public API using the league ID above:
- `GET https://api.sleeper.app/v1/league/1389753893356838912` — settings, scoring, roster slots
- `GET https://api.sleeper.app/v1/league/1389753893356838912/users` — team/owner directory
- `GET https://api.sleeper.app/v1/league/1389753893356838912/rosters` — current rosters + any locked keepers
- `GET https://api.sleeper.app/v1/draft/1389753893356838913` — 2026 draft settings
- `GET https://api.sleeper.app/v1/league/1257451899603402752/drafts` — prior season (2025) league/draft IDs
- `GET https://api.sleeper.app/v1/draft/1257451899603402753/picks` — full 2025 draft results, used to compute every player's 2026 keeper cost

Just re-run the same calls (or ask Claude to) anytime rosters change and this needs updating.
