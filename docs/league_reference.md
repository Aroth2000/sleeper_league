# Sunday Scaries Keeper League — Reference Doc

**Platform:** Sleeper | **League ID:** `1389753893356838912` | **Season:** 2026 (Year 3 of the league)
**Data pulled:** August 5, 2026, via Sleeper's public read-only API (no login needed — just the league ID above; endpoints listed at the bottom if this needs refreshing later).

---

## 1. Season timeline (so nobody gets confused by "Season 2" language)

- **Year 1 (2024 season):** original league, previous keeper/flex setup (2 flex spots, per the "Season 2 Changes" doc referencing what changed *away from*).
- **Year 2 (2025 season):** commissioner's "Season 2 Changes" took effect — flex dropped from 2 spots to 1, waivers were still rolling. Confirmed in Sleeper's actual 2025 draft settings (`slots_flex: 1`, `slots_super_flex: 1`, 7 bench spots).
- **Year 3 (2026 season — the upcoming draft):** this is what we're prepping for. Sleeper's live pre-draft settings had shown `slots_flex: 2`, which would have been a change back up from 2025's 1 FLEX. **RESOLVED 2026-08-24 — Andrew confirmed the league is in fact dropping back to 1 FLEX this year**, matching the "Season 2 Changes" doc, not the 2-FLEX setting Sleeper was showing. See §2 for the final roster shape. This lowers RB/WR/TE flex-demand league-wide versus what a 2-FLEX draft would need — one fewer flex-eligible bat per team, 10 fewer league-wide flex-starter slots than the 2-FLEX model assumed.

---

## 2. Core league settings (2026, as configured in Sleeper)

- 10 teams, Superflex (`scoring_type: 2qb`)
- Draft: **CORRECTED, confirmed live 2026-08-23 via API + in-app screenshot — Monday, Aug 24, 2026, 8:00pm ET** (`start_time` epoch `1787616007000`), snake, CPU autopick on. **Draft length was listed as 16 rounds pre-draft; the actual completed draft ran 15 rounds** (150 total picks) — see the POST-DRAFT UPDATE at the bottom of this doc. Draft order was still `null` in the API pre-draft (Sleeper hadn't published team-slot assignments yet); the owner-supplied slot order in §8 is the confirmed source for who picked where, and it matched the real draft exactly.
- Roster: **CONFIRMED BY ANDREW 2026-08-24 — dropped to 1 FLEX this year**, matching the "Season 2 Changes" doc rather than what Sleeper's settings showed pre-draft. Final: **QB, RB, RB, WR, WR, TE, FLEX, SUPER_FLEX, DEF** starting (**9 starters**, not 10). **Bench: RESOLVED post-draft — 6 spots.** (9 starters + 6 bench = 15, which now cleanly matches the actual 15-round draft; the pre-draft arithmetic flag about a mismatch with a 16-round draft is moot now that the real round count is known.)
- Playoffs: top 6 teams, playoffs start week 15
- Trade deadline: week 13
- Draft pick trading: **allowed**
- Waivers (Season 3 change): **reverse-standings rolling** (worst record gets first priority each week, replacing the old rolling-waivers system)
- DEF scoring: known to be **overpowered/buggy** last year — commissioner flagged "Fix Def scoring (TBD)" for this season. Fix status was still unconfirmed as of draft night; don't trust old DEF fantasy totals until this is confirmed fixed.

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

## 4. Keeper rules (final, as corrected 2026-08-24 — see `system/skill/reference/keepers.md` for the full rationale)

- Keep up to **3 players**
- Cost to keep a player, **first time kept**: the round he was drafted the previous year.
- Cost to keep, **every consecutive year after that**: **N-1** — one round cheaper in number than what he cost last year. *(Corrected 2026-08-24; earlier versions of this doc had this as a flat/carried-forward round — that was wrong.)*
- **Cannot keep 1st-round picks** — this restriction applies only to a player's *original* draft round. A keeper cost that escalates up into Round 1 via the N-1 rule is valid; that's simply the player's last eligible keeper year, since there's no R0 to escalate to.
- Keeping a player originally added as a **free agent/waiver pickup** (never drafted) costs a **12th-round pick** (flat, does not escalate)
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

Cost = round they were drafted in 2025 (first-time keep), or **N-1** off the round they were *kept at* in 2025 if they were already a keeper last year (marked "kept '25" below — corrected 2026-08-24, see §4). Players not found in the 2025 draft are FA/rookie adds and would cost a 12th-round pick to keep. 1st-round-*drafted* players are **not keeper-eligible**, though an N-1-escalated cost reaching R1 is valid (see §4).

### Andrew's team (andrewroth32)
| Player | Pos | 2026 keeper cost | Note |
|---|---|---|---|
| Puka Nacua | WR | R2 | kept '25 (would be N-1 → R1 if kept again; not kept — see below) |
| Kenneth Walker | RB | R4 | first-time keep — **kept** |
| Mike Evans | WR | R4 | now on San Francisco 49ers (signed FA, 3yr/$42M) — not kept |
| Tetairoa McMillan | WR | R5 | not kept |
| DeVonta Smith | WR | R6 | not kept |
| Travis Kelce | TE | R7 | not kept |
| Joe Mixon | RB | R8 | effectively unrosterable — unsigned, chronic foot/circulation issue; not kept |
| Jordan Mason | RB | R10 | not kept |
| Bo Nix | QB | **R11** (was R12, N-1 corrected) | kept '25 — **kept** |
| Javonte Williams | RB | R13 | not kept |
| Jameson Williams | WR | **R13** (was R14, N-1 corrected) | kept '25 — **kept** |
| Ashton Jeanty | RB | **N/A** | 1st-round pick — not keeper eligible |
| 4 unnamed bench/depth pieces | — | R12 (FA cost) | never drafted in 2025 |

**Final decision (locked 2026-08-24):** Andrew kept **Kenneth Walker III (R4), Bo Nix (R11), and Jameson Williams (R13)**. Puka Nacua and Mike Evans both went back into the open pool. Full reasoning: true workhorse RBs (Walker) are the league's scarcest commodity, while an elite WR tier (Puka-caliber) was approximable with Andrew's own Round 1 pick — see `system/skill/reference/keepers.md` for the complete writeup.

### League-wide keeper landscape — **RESOLVED, see §9 for the final locked board**
All 10 teams' keepers locked and confirmed by 2026-08-24 (two independent live API fetches, byte-identical). The full final board with N-1-corrected costs is in §9 below — this early section's "likely candidate" guesses from the Aug 5 pull are superseded.

---

## 7. Draft strategy takeaways (full discussion from Aug 5, 2026, updated through draft night)

- QB is a land grab in this superflex format — 15-18 QBs will be needed leaguewide once backups are counted, so don't wait on QB2 the way you would in a 1-QB league.
- **CORRECTED 2026-08-24 — single-flex, not double-flex.** The league dropped to 1 FLEX + 1 SUPERFLEX this year (confirmed by Andrew, see §1/§2), not the 2-FLEX setup this doc originally modeled. RB/WR/TE depth still matters more than a standard 1-QB format because of the SUPERFLEX slot, but noticeably less than a 2-FLEX draft would have demanded.
- Half-point-per-first-down favors possession/chain-moving players over pure deep threats — nudge personal rankings accordingly.
- Bench: **6 spots, resolved post-draft** (matches the actual 15-round draft exactly — 9 starters + 6 bench = 15).
- Up to 30 draft picks leaguewide could disappear into keeper slots — expect real gaps in the live draft board relative to ADP, especially rounds 2-14 given how many cheap keepers are floating around (see §6/§9).
- Draft pick trading is allowed — a good lever if you'd rather cash in a keeper-eligible player's draft slot for extra picks from a team that gutted its draft with keepers.
- Reverse-standings waivers reward patience — a rough start actually improves waiver priority rather than hurting it, so leaning bench-heavy at RB (highest injury churn) is reasonable.
- Don't trust old DEF fantasy scoring — the scoring bug is being fixed; treat DEF as a late-round dart throw.

---

## 8. LIVE TRACKER: draft slot selection (update as it happens)

**✅ FULL DRAFT ORDER CONFIRMED (Aug 11, 2026) — reported directly by Andrew from the actual league draft order, not derived from our reverse-PF prediction model.** This matched the real draft exactly.

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

**RESOLVED: Andrew drafted from SLOT 8** — matches the real completed draft exactly (verified via post-draft pick fetch: pick 8 was Andrew's first selection, Christian McCaffrey).

**Slot 8 pick map — as modeled pre-draft, after the N-1 keeper-cost rule correction (verified accurate against the real draft):**

Andrew corrected the keeper-cost rule on 2026-08-24: a repeat keeper costs **N-1** (one round
cheaper in number than last year), not a flat carried-forward round. That changed which two of
Andrew's own picks were forfeited — **Bo Nix moved from R12→R11 and Jameson Williams from R14→R13**,
so the forfeiture shifted from picks 113/133 to **108/128**. This modeling was confirmed exactly
correct by the actual draft: pick 33 (Kenneth Walker III), pick 108 (Bo Nix), and pick 128 (Jameson
Williams) all auto-filled as keeper picks, with 113 and 133 live as predicted.

| Round | Overall pick | Status |
|---|---|---|
| R1 | 8 | live |
| R2 | 13 | live |
| R3 | 28 | live |
| R4 | 33 | **forfeited — Kenneth Walker III keep** |
| R5 | 48 | live |
| R6 | 53 | live |
| R7 | 68 | live |
| R8 | 73 | live |
| R9 | 88 | live |
| R10 | 93 | live |
| R11 | 108 | **forfeited — Bo Nix keep (R11, was R12)** |
| R12 | 113 | live |
| R13 | 128 | **forfeited — Jameson Williams keep (R13, was R14)** |
| R14 | 133 | live |
| R15 | 148 | live |

13 live picks + 3 keepers = 16 — this table was built against the pre-draft assumption of a 16-round draft. **The actual draft ran 15 rounds**, so Andrew's real final live pick was **148 (R15)**; there was no R16/pick 153 in the real draft. See the POST-DRAFT UPDATE at the bottom of this doc and `draft_report_2026.md` for what Andrew actually took at each of these picks.

**Gap/risk model (as modeled pre-draft):** the nominal gap between any two of
Andrew's picks was modeled as fixed — always exactly 4 (same-round-pair turns) or 14
(cross-round-pair turns) picks — regardless of keepers; verified against the real, completed 2025
draft (`system/raw/draft_2025_picks.jsonl`: all 160 picks that year have unique contiguous `pick_no`s,
every real keeper pick occupied its normal slot instead of being skipped). This mechanic held for the
2026 draft too.

| Andrew's pick | Gap to next | Nominal picks between | Live/uncertain | Pre-known (keeper) |
|---|---|---|---|---|
| 8 | 13 | 4 | 3 | 1 — #9 Carluccio→Bijan Robinson |
| 13 | 28 | 14 | 12 | 2 — #15 Chow→Kyren Williams, #23 Semowo→Cook |
| 28 | 33 (own keeper) | 4 | 2 | 2 — #31 Mudse→Prescott, #32 Carluccio→Caleb Williams |
| 33 (own keeper) | 48 | 14 | 10 | 4 — #34 Deecher→Jayden Daniels, #43 Semowo→Rice, #44 Palmeri→Adams, #46 Chow→McBride |
| 48 | 53 | 4 | 4 | 0 |
| 53 | 68 | 14 | 12 | 2 — #57 Palmeri→Flowers, #65 Crisileo→Bowers |
| 68 | 73 | 4 | 4 | 0 |
| 73 | 88 | 14 | **14 — fully live, the single highest-risk stretch on the board** | 0 |
| 88 | 93 | 4 | 4 | 0 |
| 93 | 108 (own keeper) | 14 | 11 | 3 — #100 Crisileo→Pitts, #102 Habicht→Skattebo, #107 Deecher→Egbuka |
| 108 (own keeper) | 113 | 4 | 2 | 2 — #110 Mudse→Irving, #111 Mudse→Chase Brown |
| 113 | 128 (own keeper) | 14 | 9 | 5 — #116 Crisileo→Maye, #117 Palmeri→Dowdle, #119 Habicht→Johnston, #120 Crisileo→Corum, #121 Dustin→Smith-Njigba |
| 128 (own keeper) | 133 | 4 | 3 | 1 — #129 Carluccio→Dart |
| 133 | 148 | 14 | 12 | 2 — #136 Crisileo→Burden, #139 Habicht→Stevenson |

**Reframed takeaway:** picks 73→88 was modeled as a fully live 14-pick stretch with zero pre-known
picks — the single highest-risk gap on the entire board. Picks 28→33 and 108→113 were tied as the
safest waits (2 live each). Round 7 (picks 61–70) had zero forfeits league-wide. This all played out
as modeled — see `draft_report_2026.md` for what Andrew and every other team actually did with these
windows.

**Roster needs after keepers (pre-draft):** QB2 (for SUPER_FLEX), RB2, WR2, TE, 1x FLEX, DEF, plus bench (6, resolved). Andrew entered the draft with no tight end, and only one non-keeper RB and one non-keeper WR of note.

---

## 9. LIVE TRACKER: keeper decisions by team

**✅ ALL 10 TEAMS LOCKED — confirmed by two independent live Sleeper API fetches, 2026-08-23 ~23:57
UTC and 2026-08-24 ~00:02 UTC, byte-identical both times.** The keeper deadline (Sun Aug 23, 8:00pm
ET, confirmed via in-app screenshot) has passed. This table is the real, locked result — several teams did **not** match the prior guesses (e.g. havicht kept none of the three previously-guessed names; pdustin kept none of the three previously-guessed names either).

**Costs shown are N-1 corrected** (see §4 and `system/skill/reference/keepers.md` for the full rule
and rationale). 13 of these 29 keepers were repeat keepers (also kept in 2025) and escalate one round
cheaper-in-number than a flat model would show; the other 16 were first-time keeps in 2025 and are
unaffected. Escalated rows marked below.

| Team | Owner | Keepers (2026 cost, N-1 corrected) |
|---|---|---|
| (Andrew) | andrewroth32 | Kenneth Walker III (R4), **Bo Nix (R11, was R12)**, **Jameson Williams (R13, was R14)** |
| Pabst Interference | tlekes | James Cook (R3), Rashee Rice (R5) — **used only 2 of 3 slots**, both first-time keeps |
| Water, Barkley, and Hops | havicht | Cam Skattebo (R11), Quentin Johnston (R12, FA add), Rhamondre Stevenson (R14) — all first-time |
| (jomud) | jomud | Dak Prescott (R4, first-time), **Bucky Irving (R11, was R12)**, **Chase Brown (R12, was R13)** |
| Glizzy Guzzler | LoochCarluccio | **Bijan Robinson (R1, was R2 — his LAST eligible keeper year)**, Caleb Williams (R4, first-time), Jaxson Dart (R13, first-time) |
| Mass General Hospital | pdustin | Kyle Pitts (R10, first-time), Blake Corum (R12, FA add), **Jaxon Smith-Njigba (R13, was R14)** |
| Still at RPI | PeterCrisileo | **Brock Bowers (R7, was R8)**, **Drake Maye (R12, was R13)**, Luther Burden (R14, first-time) |
| Ethan's Younglings | Edeecher | **Jahmyr Gibbs (R1, was R2 — his LAST eligible keeper year)**, **Jayden Daniels (R4, was R5)**, Emeka Egbuka (R11, first-time) |
| (DannyBC1) | DannyBC1 | **Amon-Ra St. Brown (R1, was R2 — his LAST eligible keeper year)**, **Trey McBride (R5, was R6)**, **Kyren Williams (R2, was R3)** |
| Big Mommy Milkers (UCSF) | jpalmeri1616 | Davante Adams (R5, first-time), Rico Dowdle (R12, FA add), Zay Flowers (R6, first-time) |

Round-by-round forfeit counts, recomputed (how many of the 10 teams are pre-filled that round):
**R1 3** (Gibbs, Bijan Robinson, Amon-Ra St. Brown all moved here), R2 1, R3 1, R4 4, R5 3, R6 1,
R7 1, **R8 0**, **R9 0**, R10 1, R11 4, **R12 5 (heaviest)**, R13 3, R14 2, **R15 0**.
Round 1 carried real forfeits for the first time (previously 0 under the old model) — three teams were
pre-filled on their very first pick. Rounds 8, 9, and 15 were fully live.

---

## 10. LIVE TRACKER: players confirmed falling back into the draft pool

**✅ ALL 10 TEAMS RESOLVED, 2026-08-24** — every non-DEF roster player who is *not* one of that
team's 3 (or fewer) locked keepers returned to the open pool for the live draft. Resolved against the
same live roster fetch as §9, names/teams cross-checked through `players_cache.json`.

| Team | Non-keeper players returning to the pool |
|---|---|
| (Andrew) | Puka Nacua, Ashton Jeanty (R1-ineligible regardless), Mike Evans, Tetairoa McMillan, DeVonta Smith, Travis Kelce, Joe Mixon (unsigned), Jordan Mason, Javonte Williams, Kirk Cousins, Jacoby Brissett, Michael Wilson, Colby Parkinson |
| Pabst Interference (tlekes) | Lamar Jackson (R1-ineligible), A.J. Brown, Khalil Shakir, Jordan Addison, Xavier Worthy, Jake Ferguson, Aaron Rodgers, Daniel Jones, Carson Wentz, Kareem Hunt (unsigned), Chris Rodriguez, Audric Estime, Adonai Mitchell, Ryan Flournoy |
| Water, Barkley, and Hops (havicht) | Josh Allen (R1-ineligible), Saquon Barkley, Josh Jacobs, DJ Moore, Mark Andrews, David Montgomery, Bryce Young, Chris Godwin, Jayden Reed, Marvin Harrison, Dallas Goedert, Darnell Mooney |
| (jomud) | Drake London (R1-ineligible), Patrick Mahomes, Tee Higgins, J.J. McCarthy, Rome Odunze, Cam Ward, Jaylen Warren, Dalton Kincaid, Tucker Kraft, Nico Collins, Juwan Johnson, Kenny Gainwell, Tyler Allgeier |
| Glizzy Guzzler (LoochCarluccio) | CeeDee Lamb (R1-ineligible), Breece Hall, Jordan Love, Malik Nabers, Tyler Warren, Quinshon Judkins, Chris Olave, Brian Thomas, Wan'Dale Robinson, Isaiah Davis, Kimani Vidal, Jacory Croskey-Merritt |
| Mass General Hospital (pdustin) | Joe Burrow (R1-ineligible), Justin Jefferson, Baker Mayfield, Derrick Henry, T.J. Hockenson, Stefon Diggs, Tyrone Tracy, Shedeur Sanders, Troy Franklin, Kayshon Boutte, Oronde Gadsden, Woody Marks |
| Still at RPI (PeterCrisileo) | Jalen Hurts (R1-ineligible), Garrett Wilson, Omarion Hampton, TreVeyon Henderson, RJ Harvey, Courtland Sutton, George Pickens, Ladd McConkey, Jakobi Meyers, Matthew Stafford, Chig Okonkwo, Jaydon Blue, Michael Mayer |
| Ethan's Younglings (Edeecher) | Ja'Marr Chase (R1-ineligible), Justin Herbert, De'Von Achane, D'Andre Swift, Sam Darnold, Hunter Henry, Trey Benson, Jaylen Wright, Quinn Ewers, Harold Fannin, Kyle Monangai, Michael Carter, Christian Watson |
| (DannyBC1) | Jonathan Taylor (R1-ineligible), C.J. Stroud, DK Metcalf, Deebo Samuel, Travis Etienne, Geno Smith, David Njoku, Najee Harris, Michael Pittman, Jaylen Waddle, Trevor Lawrence, Tez Johnson, Tyjae Spears |
| Big Mommy Milkers (jpalmeri1616) | Christian McCaffrey (R1-ineligible), Brock Purdy, Jared Goff, Aaron Jones, George Kittle, Terry McLaurin, Tony Pollard, Jauan Jennings, Keenan Allen (unsigned), Tyler Shough, Zonovan Knight |

That's ~123 players confirmed back in the pool across the other 9 teams alone — this was the
authoritative pre-draft availability list; see `draft_report_2026.md` for who actually drafted whom.

---

## 11. Player value alert — directly affected Andrew's keeper decision

**Kenneth Walker III (on Andrew's roster, 2026 keeper cost R4) signed with the Kansas City Chiefs in free agency after being named Super Bowl LX MVP.** Multiple outlets (ESPN, NFL.com, Fox Sports) reported he got one of the largest RB contracts in league history and was expected to see "the largest workload of his career" behind Kansas City's line, playing alongside Patrick Mahomes — a major offensive upgrade from splitting Seattle's backfield with Zach Charbonnet. This substantially raised his redraft/keeper value and factored directly into keeping him.

Side effect worth knowing: Seattle's backfield opened up because Walker left — see rookie Jadarian Price in §12, who directly benefited (and was in fact drafted by Andrew at pick 68 — see `draft_report_2026.md`).

---

## 12. 2026 rookie class — names worth knowing (pulled Aug 5, 2026)

Sourced from CBS Sports, Fox Sports, and other fantasy outlets' rookie rankings. These were real draft-day considerations, not just waiver stashes, since this was a full redraft.

**Running backs**
- Jeremiyah Love (ARI, 3rd overall) — the headline rookie RB, 3-down profile, but stuck on a weak Arizona team.
- Jadarian Price (SEA, 32nd overall) — benefits directly from Kenneth Walker's departure (see §11) and Zach Charbonnet's injury recovery; one of the best pure opportunity spots of any rookie.
- Kaelon Black (SF, 3rd round) — CMC's backup; boom potential only on injury.
- Nicholas Singleton (TEN), Jonah Coleman (DEN), Kaytron Allen (WAS) — depth-chart dependent.

**Wide receivers**
- Carnell Tate (TEN, 4th overall) — Titans' No. 2 WR opposite Chris Olave; upside tied to Cam Ward's development.
- Jordyn Tyson (NO, 8th overall) — complements Chris Olave in New Orleans, should see volume as defenses key on Olave.
- Kaelon Boston (CLE, 39th overall) — big-bodied (6'4"/212) target in a Browns WR room with no proven touchdown scorer.
- Makai Lemon (PHI), KC Concepcion (CLE), Omar Cooper Jr. (NYJ) — depth WR3/4 dynasty-flavored options.

**Tight ends**
- Kenyon Sadiq (NYJ) — clearest immediate-opportunity rookie TE, Jets' TE room was unproductive last year.
- Eli Stowers (PHI) — could carve into Dallas Goedert's role/red-zone work.
- Justin Joly (DEN), Max Klare (LAR) — long-term stashes, murkier 2026 paths.

**Quarterbacks** (lower redraft urgency in a 10-team superflex unless a starting job opens)
- Fernando Mendoza (LV) — buried behind Kirk Cousins for now, dynasty-only.
- Ty Simpson (LAR), Carson Beck (ARI) — monitor camp battles.

---

## 13. News sweep — pre-draft research archive (Aug 6-7, 2026)

The full research sweep from early August covering all 32 NFL teams, Andrew's keeper-eligible players, other teams' likely keepers, and trade/handcuff/rookie/QB-battle themes. Kept here as the historical record of what informed the keeper decision — see `news_sweep_full_report.md` for the complete findings and `gap_fill_plan.md` for the audit trail.

**Headline findings that held up:** Mike Evans signed with the San Francisco 49ers as their new WR1 (3yr/$42M). Travis Kelce confirmed returning for a 14th season as Kansas City's unchallenged TE1. Joe Mixon remained unsigned with no known suitor, a chronic foot/circulation issue, and was treated as effectively unrosterable.

**Final pre-draft recommendation that was acted on:** keep Kenneth Walker III as the 3rd keeper (over Puka Nacua and Mike Evans) — true workhorse RBs were judged the league's scarcest commodity, while an elite WR tier was approximable via Andrew's own Round 1 pick. Bo Nix (R11) and Jameson Williams (R13) were locked without hesitation as clean surplus-value keeps. This is exactly what happened — see §6.

---

## 14. Open questions to confirm with the commissioner — status as of post-draft

1. ~~Is FLEX really 2 spots for 2026, or should it be 1?~~ **RESOLVED 2026-08-24 by Andrew: 1 FLEX**, matching the "Season 2 Changes" doc. Sleeper's pre-draft setting showing 2 did not hold, and the real draft ran on the 1-FLEX/9-starter roster shape.
2. Has the DEF scoring fix actually been applied? **Still unconfirmed** as of draft night — treat DEF value cautiously into Week 1 until it's verified in-season.
3. ~~Keeper decision deadline~~ **RESOLVED 2026-08-23:** Sun, Aug 23 @ 8:00pm ET. All 10 teams' keepers locked in Sleeper — see §9 and `system/skill/reference/keepers.md`.
4. **NEW, resolved post-draft:** the pre-draft "16 rounds vs. 6-bench arithmetic mismatch" flag is closed — the real draft ran **15 rounds**, matching 9 starters + 6 bench exactly.

---

## 15. How this was compiled (for refreshing later)

Pulled via Sleeper's free, no-auth public API using the league ID above:
- `GET https://api.sleeper.app/v1/league/1389753893356838912` — settings, scoring, roster slots
- `GET https://api.sleeper.app/v1/league/1389753893356838912/users` — team/owner directory
- `GET https://api.sleeper.app/v1/league/1389753893356838912/rosters` — current rosters + any locked keepers
- `GET https://api.sleeper.app/v1/draft/1389753893356838913` — 2026 draft settings and (post-draft) results
- `GET https://api.sleeper.app/v1/draft/1389753893356838913/picks` — full 2026 draft results (150 picks), used to build `draft_report_2026.md`
- `GET https://api.sleeper.app/v1/league/1257451899603402752/drafts` — prior season (2025) league/draft IDs
- `GET https://api.sleeper.app/v1/draft/1257451899603402753/picks` — full 2025 draft results, used to compute every player's 2026 keeper cost

Just re-run the same calls (or ask Claude to) anytime rosters change and this needs updating.

---

## POST-DRAFT UPDATE (2026-08-25)

The draft happened as scheduled Monday Aug 24, 8:00pm ET, and completed the same night. Key resolutions:

- **Actual draft length: 15 rounds (150 total picks)**, not the 16 assumed pre-draft. This closes out the bench-count ambiguity flagged throughout this document — 9 starters + 6 bench = 15, exact match, no wrinkle.
- All three of Andrew's keepers (Kenneth Walker III, Bo Nix, Jameson Williams) auto-filled at picks 33, 108, and 128 exactly as modeled in §8.
- The pre-draft Round 1 read expected Puka Nacua to still be available at pick 8 — instead he went 3rd overall (to Pabst Interference/tlekes), and Christian McCaffrey fell to Andrew at pick 8 instead.
- Full team-by-team results for all 10 rosters, what everyone did right/wrong, and a league-wide power ranking live in **`draft_report_2026.md`**, generated the night of the draft from the actual completed pick data pulled via the Sleeper API.
