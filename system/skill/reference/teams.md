# Teams and owners

`roster_id` is the join key across every Sleeper payload. `user_id` is what `users.json` keys on.
Use display names in anything Andrew reads — he thinks in owner handles, not roster ids.

| roster_id | Owner (Sleeper handle) | Team name | user_id | Waiver pos at config |
|---|---|---|---|---|
| 1 | tlekes **(commissioner)** | Pabst Interference | 1123669553063526400 | 10 |
| **2** | **andrewroth32** | *(none set)* | 1128203360286429184 | **4** |
| 3 | havicht | Water, Barkley, and Hops | 1128898667324239872 | 6 |
| 4 | jomud | *(none set)* | 1129508145568686080 | 8 |
| 5 | LoochCarluccio | Glizzy Guzzler | 603841382339108864 | 3 |
| 6 | pdustin | Mass General Hospital | 869724998703763456 | 7 |
| 7 | PeterCrisileo | Still at RPI | 870744736284196864 | 5 |
| 8 | Edeecher | Ethan's Younglings | 869654771978641408 | 9 |
| 9 | DannyBC1 | *(none set)* | 1131700966283177984 | 1 |
| 10 | jpalmeri1616 | Big Mommy Milkers (UCSF) | 1133830654808072192 | 2 |

> **Waiver positions above are a preseason snapshot only.** They move every single week — a team
> that wins a claim drops to the back. Always read the live value from
> `rosters[].settings.waiver_position`, or from `waiver_order` / `teams_picking_ahead_of_andrew` in
> the current `state/week_N.json`. Never quote the table above as this week's order.

## Rival notes worth carrying

- **LoochCarluccio (Glizzy Guzzler)** — the only team that locked keepers early on Sleeper. That
  makes his roster the most predictable and his discards the most reliably known.
- **jomud** — QB-hoarder profile in a superflex league. Expect him to be the competing bidder on any
  quarterback that hits the wire, and a natural trade partner if Andrew ends up QB-rich.
- **tlekes** — commissioner. Route rules questions (waiver clock, DEF scoring fix, keeper deadline)
  to him; those are the open questions blocking parts of this system.

## Keeper landscape at config time (2026 preseason)

Only Glizzy Guzzler had actually locked keepers in Sleeper. Everything else is "likely candidates
based on cost vs value" — treat as a prior, not as fact, and overwrite it the moment the `keepers`
field on a roster goes non-null.

| Owner | Likely / locked keepers |
|---|---|
| LoochCarluccio | **LOCKED:** Bijan Robinson (R2), Caleb Williams (R4), Jaxson Dart (R13) |
| havicht | Saquon Barkley (R3), Josh Jacobs (R5), David Montgomery (R9) |
| jomud | Nico Collins (R5), Bucky Irving (R12), Chase Brown (R13) |
| pdustin | Justin Jefferson (R2), Derrick Henry (R4), Jaxon Smith-Njigba (R14) |
| PeterCrisileo | Brock Bowers (R8), Ladd McConkey (R10), Drake Maye (R13) |
| Edeecher | Jahmyr Gibbs (R2), De'Von Achane (R4), Jayden Daniels (R5) |
| DannyBC1 | Amon-Ra St. Brown (R2), Kyren Williams (R3), Trey McBride (R6) |
| jpalmeri1616 | George Kittle (R8), Terry McLaurin (R9) |
| tlekes | A.J. Brown (R2) |

Once a team locks keepers, every other non-DEF player on its roster falls back into the draft pool.
Glizzy Guzzler's confirmed fallbacks: Breece Hall, Jordan Love, Malik Nabers, Tyler Warren, Quinshon
Judkins, Chris Olave, CeeDee Lamb, Brian Thomas.

## The opponent intent model (Part 4, made deterministic)

`system/analysis/opponent_pressure.py` scores four distinct pressures per team, per position:

- **vacancy** — a starter is out, doubtful, suspended, or on bye. Highest signal; straight from the
  Sleeper injury field.
- **performance** — a starter is below replacement over a rolling 2–3 week window. Factual, computed
  from `/matchups` through `scoring.py`.
- **role** — losing snaps, routes or targets *before* the box score reflects it. **Cannot be derived
  from Sleeper data.** It is accepted only as an external input from the news agents, never invented
  in code. Catching role pressure a week before the points collapse is where the actual edge is.
- **depth** — no viable replacement on their own bench, so the fix must come from outside.

```
need     = w_v*vacancy + w_p*performance + w_r*role
pressure = need * (0.35 + 0.65*depth) * ACTION_MULT[pos]
```

`need` says the position is broken; `depth` says they cannot fix it internally. A team with a hurt
RB1 and a good handcuff has high need and low external pressure — they plug it in-house and never
touch the wire. That is why depth multiplies rather than adds.

Crossed against the ranked free-agent pool and the live priority order, this yields a concrete
prediction per rival, and occasionally a **blocking** opportunity — a cheap claim on a player a rival
desperately needs, worth more than the roster spot costs. It also drives trade timing: a team with
acute sustained need where Andrew has surplus is a team that will overpay.
