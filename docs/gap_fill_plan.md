# Gap-Fill & Re-Synthesis Plan — Aug 6/7 2026 News Sweep

Purpose: this file is the persistent record of what's broken in `news_sweep_full_report.md` / `league_reference.md`, what fixes it, and exactly what to run next — so if a usage limit interrupts this mid-way, whoever (or whatever future turn) picks this back up can do so from this file alone without re-deriving anything.

## Audit method (already done)

Grepped `news_sweep_full_report.md` for incompleteness markers (`incomplete`, `unresolved`, `no live sources`, `research gap`, `verify`, `Wikipedia`, `tool fail`, `search budget`, etc.) and manually read the flagged sections plus the corresponding team-sweep entries to check whether the team-level research (which was NOT flagged as incomplete) already answers the player-level gap.

## Findings: full list of gaps

### Category 1 — FALSE gaps: already answered by the team-sweep section, just never cross-referenced by the roster-synthesis agent

The "Andrew's Roster" section flagged these 5 players as "research incomplete this cycle." In every case, the 32-team sweep (a separate, successful agent) already contains the answer:

| Player | Roster section said | What the team sweep actually found |
|---|---|---|
| Jameson Williams (WR) | incomplete, no live sources | Detroit Lions section: "Amon-Ra St. Brown and Jameson Williams entrenched 1-2" — still elite WR2, no change |
| Mike Evans (WR) | incomplete, no live sources | **Tampa Bay section: "Mike Evans is gone (signed with 49ers)."** **San Francisco section: "Mike Evans (3-yr/$42M FA signing) is the new WR1" (minor quad issue).** This is a big one — Evans changed teams and the old roster note (still listing him as Buccaneers) is wrong. |
| Tetairoa McMillan (WR) | incomplete, no live sources | Carolina Panthers section: "Tetairoa McMillan is the clear WR1 (camp standout); Jalen Coker locked in as extended WR2" |
| DeVonta Smith (WR) | incomplete, no live sources | Philadelphia Eagles section: A.J. Brown traded to Patriots — "DeVonta Smith inherits the clear WR1/target lead" |
| Travis Kelce (TE) | incomplete, roster/retirement status unconfirmed — flagged as "the single most urgent verification item on the roster" | Kansas City Chiefs section: "Travis Kelce confirmed returning for a 14th season (GM Veach: 'not going out like this'), remains clear TE1" — resolved, he's playing |

**Fix:** no new web research needed for these 5. Rewrite the "Andrew's Roster" section (and any downstream reference to them) using the team-sweep data already in hand. This is a synthesis/editing task, not a research task — can be done directly, or via one cheap agent if preferred for consistency.

### Category 2 — REAL gap: needs a fresh, targeted research agent

| Item | Problem | Plan |
|---|---|---|
| Joe Mixon (RB) | No team sweep entry claims him (he's not on any of the 32 teams' offensive summaries). Roster section repeated the same unconfirmed "released by Houston, reportedly unsigned" line from the prior partial run — never actually independently re-verified. This is the one true unresolved player. | Spawn one fresh agent with a narrowly-targeted prompt: "As of August 2026, is Joe Mixon (RB) currently signed to any NFL team? If yes, which team, what is his depth-chart/role status, and any injury update. If no, confirm he is a free agent and note any reported team interest." |

### Category 3 — Soft quality gap (lower priority, optional refresh)

| Item | Problem | Plan |
|---|---|---|
| Jacksonville Jaguars team report | Explicitly self-flagged: "this team's research relied on Wikipedia data rather than live camp beat coverage — verify latest camp reports before finalizing rankings." Content looks plausible (matches the independent findings from the Aug 5 partial run about Etienne/Bigsby departures) but sourcing is weaker than the other 31 teams. | Optional: spawn one refresh agent forcing live WebSearch/WebFetch use (same retry-forcing technique used for the Chiefs last time) to confirm/upgrade this team's report. Not roster-critical (no Sunday Scaries player is a Jaguar), so lower priority than Mixon. |

### Category 4 — Not a gap, just monitor (no agent needed)

- Seattle's Holani/Price RB battle and San Francisco's Guerendo/James/Black RB battle are described as genuinely unresolved in real life (camp competition still ongoing) — no amount of research fixes this, it's a "check again closer to the draft" item, not a research failure.
- Rookie Denzel Boston (CLE) — minor "verify name against other rookie-list sources" flag in the rookie deep-dive. Low stakes, not worth a dedicated agent; just carries a footnote.

## Downstream analysis that must be rewritten once the above is fixed

The final "Recommendation" section (and the corresponding Section 13 of `league_reference.md`) was written *before* the roster gaps were understood, so it:
1. Doesn't mention that **Mike Evans is now a 49er**, not a Buccaneer — this is a genuinely new, material fact about a player Andrew already owns (R4 keeper cost) that changes his value profile (new team, competing for volume with a crowded/banged-up 49ers pass-catching group, but clear WR1 role).
2. Doesn't reflect that **Travis Kelce is confirmed still playing** (14th season) rather than a retirement risk — should soften/remove the "urgent verification" flag and treat him as a normal, still-productive keeper-caliber TE.
3. Should double check whether Mike Evans' R4 cost now creates a *three-way* 3rd-keeper competition (Puka Nacua R2 / Kenneth Walker III R4 / Mike Evans R4) rather than the two-way Puka-vs-Walker framing used last time.
4. Once Joe Mixon's real status comes back, his line in the keeper-cost table and any related commentary needs a final, confident (not hedged) update.

**Plan:** after the new/backfilled facts are in hand, re-run the final-recommendation synthesis (or do it directly) with all corrected inputs, then update:
- `news_sweep_full_report.md` — Andrew's Roster section (rewrite), Joe Mixon entry (rewrite), Jacksonville entry (rewrite if refreshed)
- `league_reference.md` — Section 6 (keeper-cost table note for Mike Evans' new team), Section 9 (keeper decision row), Section 13 (recommendation — 3rd-keeper call and action list)

## Execution steps (in order)

1. [ ] Spawn 1 agent: Joe Mixon fresh research (Category 2)
2. [ ] Spawn 1 agent (optional): Jacksonville Jaguars live-source refresh (Category 3)
3. [ ] Rewrite "Andrew's Roster" section using Category 1 cross-referenced facts + new Mixon result — no new research needed for the 5 Category-1 players
4. [ ] Re-run final recommendation synthesis with corrected roster facts (Mike Evans → SF, Kelce confirmed active, updated Mixon status, potential 3-way 3rd-keeper decision)
5. [ ] Update `news_sweep_full_report.md` and `league_reference.md` with the rewritten sections
6. [ ] Deliver updated files + a plain-language summary of what changed and why, to Andrew

## Status log

- 2026-08-07: Plan written, audit complete, about to execute steps 1-2 via a small Workflow.
- 2026-08-07: Launched targeted 4-agent workflow (Mixon research + Jacksonville refresh in parallel, then roster rewrite, then recommendation rewrite). Run ID: `wf_f23dafba-f79`, script at `/home/claude/sunday_scaries/gap_fill_workflow.js`. If this gets interrupted, resume with `Workflow({scriptPath: "/home/claude/sunday_scaries/gap_fill_workflow.js", resumeFromRunId: "wf_f23dafba-f79"})` — completed agents replay from cache. Waiting on task ID `wbkgjowx3` to complete.
- 2026-08-07: **COMPLETE.** All 4 agents finished cleanly. Joe Mixon resolved conclusively (unsigned, chronic injury, reportedly told friends he believes he's done playing — treat as unrosterable). Jacksonville refreshed with live sources. Roster section and final recommendation both rewritten and merged into `news_sweep_full_report.md` and `league_reference.md` (Sections 6, 9, 13). All planned work in this plan file is done — nothing left pending.
