# What lands in Andrew's hands each Tuesday

Eight sections, in this order. The synthesis agent in `weekly.js` emits sections 1–7 as
`report_markdown` and section 8 as `state_json`; the caller writes both to disk and sends them to
Andrew. Post section 1 inline in chat regardless — that is the part he reads on a phone.

---

**1. Action card.** The top five things to do, ranked, **each in one line.** Readable in thirty
seconds. No hedging, no supporting detail — that lives below. If something is genuinely uncertain,
say so in five words, not a paragraph.

**2. Lineup card.** Start/sit for all ten slots — QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX,
DEF — with a short reason for anything non-obvious. Obvious starts need no justification. Call out
any slot where the answer flips if FLEX is really 1 instead of 2.

**3. Waiver claims, ordered.** Each with an **honest probability of landing him**, given who picks
ahead of Andrew this week. Not a wishlist — an ordered claim sheet. Include the keeper-equity flag
per target. State the waiver mode assumed (priority) and, while the clock time is unconfirmed,
repeat the submission deadline: **before Tuesday 18:00 ET**.

**4. Drop candidates.** Ranked by what is actually lost, **with keeper equity accounted for**. A
cheap 12th-round keeper is worth more than his current points suggest.

**5. Trade board.** Specific offers to specific owners, with the rationale aimed at that owner's
situation — not a generic "buy low on X". Loudest in weeks 4–8; silent after week 13.

**6. Opponent intel.** One short paragraph per rival, nine of them: what changed, what they need,
what they will likely do. Lead with the change, not with a re-description of a settled roster.

**7. Keeper-equity watchlist.** Who on Andrew's roster and on waivers is accumulating 2027 value at
a 12th-round price, plus anyone approaching the 3-consecutive-year cap.

**8. Updated state file.** The memory that makes next week cheap. Written to
`system/state/week_N.json`.

---

## State file shape

```jsonc
{
  "meta":     { "league_id", "season", "week", "generated_at", "season_phase", "waiver", ... },
  "standings":[ { "roster_id": 2, "wins": 4, "losses": 2, "pf": 812.4, "waiver_priority": 6 } ],
  "waiver_order": [...], "teams_picking_ahead_of_andrew": [...],
  "teams":    { "2": { "owner", "players", "starters", "bench", "injuries", "bye_weeks" } },
  "roster_diff": {...}, "matchups": {...}, "injuries": [...], "free_agents": {...},
  "transaction_log": [ { "week", "type", "team", "added", "dropped", "priority_used" } ],
  "opponent_model": { "9": { "pressure": {"RB":0.81,...}, "vulnerable_starters": [],
                             "predicted_claims": [], "trade_appetite": "", "confidence": "" } },
  "keeper_equity": [ { "player", "acquired", "keeper_cost_2027", "projected_value", "surplus" } ],
  "decisions_log": [ { "week", "recommended", "action_taken", "outcome" } ],
  "open_questions": [ ... ]
}
```

Two fields carry disproportionate weight:

- **`decisions_log`** makes the system accountable to itself. Each week, fill in `outcome` on last
  week's entries — did the claim we pushed actually produce? — then append this week's
  recommendations ungraded. Over a season that becomes a calibration signal and stops the system
  confidently repeating a bad heuristic.
- **`keeper_equity`** is the league-specific edge. See `keepers.md`.

## Tone and honesty rules

- **Lead with the decision, then the reason.** Andrew wants the call, not the deliberation.
- **Never pad a thin section.** If two opponent agents died, say the intel is incomplete and which
  teams are missing. A confident-sounding empty paragraph is worse than an admitted gap.
- **Every time-sensitive claim carries a named source dated inside 7 days.** Flag anything older as
  stale rather than dropping it silently.
- **Never name a free agent without confirming he is unrostered in this league.** This is the most
  damaging failure mode available — it looks authoritative and wastes a claim.
- **Open questions appear in section 8 every week until closed** — waiver clock time, DEF scoring
  fix, keeper deadline, 2026 bye weeks, FLEX 1 vs 2.
