# The Tuesday System — Design Plan for In-Season Fantasy Management

**Status: DESIGN ONLY. Nothing here is built yet.** This document is the blueprint. Implementation is broken into phases at the end so it can be built incrementally between now and Week 1.

**Goal:** one command, fired any Tuesday, that produces a complete action plan for the week — lineup, waiver claims in priority order, drop candidates, trade offers, and an intelligence brief on what all nine rivals are about to do — and that carries its own memory forward week over week without depending on a chat staying alive.

---

## Part 1 — Architecture: what primitive to use, and why

There are four building blocks available, and the honest answer is that this system needs all four, layered, because each one solves a different problem. Picking just one produces a system that fails in a specific, predictable way.

| Primitive | What it actually is | Survives a new chat? | Runs in parallel? | Callable by name? |
|---|---|---|---|---|
| **Skill** | A packaged folder of instructions plus bundled reference files, loaded into context when invoked | **Yes** — lives in your account | No, runs inline | **Yes** (`/tuesday`) |
| **Workflow** | A JavaScript orchestration script that fans out subagents with deterministic control flow | Script persists on disk; each run is ephemeral | **Yes** — ~16 concurrent | By file path |
| **Agent (subagent)** | A single worker with its own context window | No | Is the unit of parallelism | Via the Agent tool |
| **Scheduled task** | A cron trigger that starts a fresh session | **Yes** | n/a | n/a |

### Why not a skill alone

A skill's instructions execute *inline, serially, in the main conversation*. Running nine opponent analyses plus a league-wide news sweep inline is precisely what blew through the usage cap twice during draft prep. It is also slow, and if it dies halfway there is no resume — you start over from zero. A skill alone gives you portability but no muscle.

### Why not a workflow alone

A workflow is a `.js` file sitting in a container that gets reclaimed when the session ends. It has no bundled domain knowledge, cannot be invoked by name from a fresh chat, and would require you to re-supply the league ID, scoring rules, roster map, and analytical framework every single time. A workflow alone gives you muscle but no memory.

### Why not agents alone

Agents are the workers, not the manager. Firing eleven Agent calls by hand every Tuesday is the thing we are trying to automate.

### The recommendation: a skill that owns the knowledge, wrapping a workflow that owns the execution

```
/tuesday  (skill — portable, named, holds league constants + framework + output templates)
    │
    ├── reads   state/week_N-1.json          ← last week's canonical facts
    ├── runs    scripts/sync_sleeper.py      ← deterministic API pull, no LLM
    │
    └── invokes scripts/weekly.js            (workflow — parallel, resumable)
                    │
                    ├── 9x opponent agents        (sonnet — mechanical, cheap)
                    ├── 4x news/injury agents     (sonnet)
                    ├── 1x free-agent pool agent  (sonnet)
                    ├── 1x my-team agent          (sonnet)
                    │
                    ├── waiver contention model   (opus — real judgment)
                    └── final synthesis           (opus — the action card)
                    │
            writes  state/week_N.json + reports/week_N.md
```

Optionally fronted by a **scheduled task** that fires it Tuesday morning so the brief is waiting for you.

**The division of labour is the point.** The skill is *memory and procedure* — it is what makes this work in a chat opened three months from now with no history. The workflow is *muscle and resilience* — parallel enough to be fast, resumable enough to survive a usage cap mid-run. Deterministic Python handles anything that must never be hallucinated. Agents do the research that genuinely needs a model.

### Model assignment

Cost control matters here, because this runs seventeen-plus times. Roughly: sonnet for anything mechanical or retrieval-shaped (nine opponent reads, news sweeps, free-agent pool ranking); opus reserved for the two stages that require actual reasoning under uncertainty — the waiver contention model and the final synthesis. That keeps a weekly run in the range of a modest fraction of what the draft-prep sweep cost, while putting the expensive model exactly where judgment lives.

---

## Part 2 — State: the thing that makes it mature instead of seventeen one-shots

The single biggest design decision is that **the system diffs rather than snapshots.** Almost all of the value is in what *changed*: who got added and dropped, whose snap share moved, who got hurt, who quietly got out-targeted in practice. A system that re-derives the world from scratch each week is both expensive and blind to trends.

So every run loads last week's state, pulls fresh facts, computes a diff, researches mostly what changed, and writes new state.

### `state/week_N.json`

```jsonc
{
  "meta":   { "league_id": "...", "season": 2026, "week": 7, "generated_at": "...", "waiver_process_day": "Wednesday" },

  "standings": [ { "roster_id": 2, "wins": 4, "losses": 2, "pf": 812.4, "waiver_priority": 6 } ],

  "teams": {
    "2": {
      "owner": "andrewroth32",
      "players": ["..."],
      "starters": ["..."],
      "bench": ["..."],
      "injuries":  [ { "player": "...", "status": "Questionable", "since_week": 6 } ],
      "bye_weeks": { "QB": [11], "RB": [7, 9] }
    }
  },

  "transaction_log": [
    { "week": 6, "type": "waiver", "team": "DannyBC1", "added": "...", "dropped": "...", "priority_used": 3 }
  ],

  "opponent_model": {
    "9": {
      "pressure": { "RB": 0.81, "WR": 0.22, "TE": 0.05 },
      "vulnerable_starters": ["..."],
      "predicted_claims":    ["..."],
      "trade_appetite":      "desperate at RB, surplus at WR",
      "confidence": "high"
    }
  },

  "keeper_equity": [
    { "player": "...", "acquired": "waiver_week_5", "keeper_cost_2027": "R12", "projected_value": "RB2", "surplus": "very high" }
  ],

  "decisions_log": [
    { "week": 6, "recommended": "claim X over Y", "action_taken": "claimed X", "outcome": "18.4 pts, hit" }
  ],

  "open_questions": ["Confirm whether waivers are priority-based or FAAB — Sleeper settings are ambiguous"]
}
```

Two fields deserve special attention.

**`decisions_log`** makes the system accountable to itself. Each week it can grade its own prior recommendations — did the claim we pushed actually produce? Over a season that becomes a calibration signal, and it stops the system from confidently repeating a bad heuristic.

**`keeper_equity`** is the league-specific edge, explained in Part 5.

---

## Part 3 — The weekly run, phase by phase

### Phase 0 — Deterministic sync (pure Python, no model)

Everything that must be exactly right happens here, in code, with no opportunity to hallucinate. The Sleeper API is free and unauthenticated; all we need is the league ID.

| Endpoint | Gives us |
|---|---|
| `/league/{id}/rosters` | current rosters, waiver position, record, points |
| `/league/{id}/transactions/{week}` | every add, drop, waiver claim and trade — **including which priority was used** |
| `/league/{id}/matchups/{week}` | actual weekly scoring, starters vs bench |
| `/league/{id}/users` | owner names |
| `/players/nfl/trending/add` | league-wide hot waiver adds across all of Sleeper — a strong proxy for who is about to be claimed |
| `/state/nfl` | current week, so the system knows where it is without being told |

Output of this phase is a plain diff: roster changes, new injuries, standings movement, waiver priority order, and the current free-agent pool.

**Two implementation constraints already discovered and worth recording now**, because they will otherwise cost an hour of confusion later:

1. `curl` to `api.sleeper.app` is blocked by the sandbox proxy and returns a 403 on CONNECT. **WebFetch works.** Any sync code must go through WebFetch, not shell HTTP.
2. The full player dump at `/players/nfl` is roughly five megabytes and cannot be pulled through WebFetch intact. The fix is to **build the player-ID-to-name cache incrementally**: draft-pick payloads and transaction payloads both embed a `metadata` block containing first name, last name, position and NFL team. Harvesting those over time produces a local `players_cache.json` covering exactly the players this league actually touches, which is the only subset that matters. This also finally resolves the handful of unidentified bench players currently showing as raw IDs on several rosters.

### Phase 1 — Parallel intelligence gathering (sonnet, ~15 agents)

- **Nine opponent agents**, one per rival. Each gets that team's roster plus the diff plus last week's `opponent_model` entry, and returns updated pressure scores and predicted moves.
- **Four news agents**, sliced by topic rather than by team to avoid redundancy: injury report and practice participation; snap-count and target-share movers; depth-chart and role changes from beat reporting; breakout and buy-low candidates.
- **One free-agent pool agent** that ranks everyone actually available *in this league* by rest-of-season value in this specific scoring format.
- **One my-team agent** covering lineup optimisation, bye coverage, and sell-high candidates.

### Phase 2 — Cross-analysis (opus, 2 agents)

This is where the parts combine into something none of them could produce alone.

**The waiver contention model.** For every free agent worth claiming, it determines which teams ahead of Andrew in the reverse-standings priority order are likely to want that player, and therefore what the realistic probability of landing him is. This converts a flat wishlist into an *ordered* claim sheet — which is the difference between burning your priority on someone who was never going to reach you and quietly landing the player nobody else was tracking.

**The trade board.** It matches Andrew's positional surplus against each rival's acute need, and drafts specific, sendable offers with a one-line rationale aimed at that owner's actual situation.

### Phase 3 — Synthesis and output

A single action card, ordered by importance, plus the supporting detail. Format is covered in Part 6.

---

## Part 4 — The opponent intent model

This is the part you described, formalised. The intuition — *a manager whose receiver just got hurt or benched is about to hit the waiver wire* — becomes a scoring function computed per team, per position.

Four distinct pressures push a manager toward a move:

**Vacancy pressure.** A starter is injured, suspended, or on bye with no backup. Highest-signal and easiest to detect; comes straight from the Sleeper injury field plus the schedule.

**Performance pressure.** A starter is producing meaningfully below replacement level over a rolling two-to-three-week window. Computed from `/matchups`, so it is factual rather than inferred.

**Role pressure.** The subtle one, and the one you specifically called out. A player is losing snaps, routes, or targets to a teammate — or getting beaten out in practice — *before* the box score reflects it. This only surfaces through beat reporting and snap-count data, which is exactly what the news agents are for. Catching role pressure a week before the points collapse is where the actual edge is, both for your own roster and for predicting a rival's move.

**Depth pressure.** No viable replacement sits on their bench, so the need must be filled externally rather than internally.

Combined into a per-position pressure score, then crossed against the ranked free-agent pool and that team's waiver priority, this yields a concrete prediction: *this team will claim one of these two or three players this week.* Aggregated across nine rivals, it produces the contention map that drives Andrew's claim ordering — and occasionally flags a genuine blocking opportunity, where a cheap claim on a player a rival desperately needs is worth more than the roster spot costs.

It also drives trade timing. A team with acute, sustained need at a position where Andrew has surplus is a team that will overpay, and the model knows both halves of that equation.

---

## Part 5 — Two league-specific layers worth building deliberately

### Keeper equity — the biggest non-obvious edge

In this league, **a player picked up off waivers costs a 12th-round pick to keep next season.** That single rule means every in-season acquisition carries a hidden second value: not just what he does for you in Week 9, but whether he projects as a 2027 keeper at a twelfth-round price.

A breakout rookie running back claimed in Week 7 who finishes as an RB2 is a genuinely enormous asset — you keep him next year for a twelfth. The same production from a veteran you *drafted* in the third round is keepable only at third-round cost. Identical points, wildly different franchise value.

So every waiver recommendation should carry a keeper-equity flag alongside its win-now value, and late-season roster decisions — when your playoff fate is largely settled — should tilt hard toward stashing ascending young players over marginal veteran upgrades. The system should maintain this list all year and hand you a ranked keeper-equity board in Week 16 rather than making you reconstruct it in August.

It should also track the **three-consecutive-year cap** on each current keeper, so you know in advance which players are about to age out of eligibility. Bo Nix and Jameson Williams both hit their final eligible year in 2027 if kept again this season.

### Season-phase awareness

The same question deserves different answers in Week 2 and Week 12. The system should know which phase it is in and change its own defaults accordingly.

**Weeks 1–3** are a sample-size trap. Judge opportunity metrics — snaps, routes run, target share — not fantasy points, and resist cutting a good player for a one-week wonder.

**Weeks 4–8** are the trade window. Rival managers are forming strong opinions off small samples, which is exactly when buy-low and sell-high offers land. This is the phase to be most aggressive on the trade board.

**Weeks 9–13** are playoff positioning, and the **trade deadline falls in Week 13** — a hard wall for any consolidation move. This is also when to start weighting Weeks 15–17 schedules rather than season-long averages.

**Weeks 14–17** are the playoffs (top six teams, starting Week 15). Streaming and matchup optimisation dominate, and if elimination becomes likely the entire objective flips to keeper-equity accumulation for next season.

---

## Part 6 — What lands in your hands each Tuesday

1. **Action card** — the top five things to do, ranked, each in one line. Readable on a phone in thirty seconds.
2. **Lineup card** — start/sit for every slot, with a short reason for anything non-obvious.
3. **Waiver claims, ordered** — with an honest probability of landing each, given who picks ahead of you.
4. **Drop candidates** — ranked by what you lose, with keeper equity accounted for.
5. **Trade board** — specific offers to specific owners, with the rationale aimed at their situation.
6. **Opponent intel** — a short paragraph per rival: what changed, what they need, what they will likely do.
7. **Keeper-equity watchlist** — who on your roster and on waivers is accumulating 2027 value.
8. **Updated state file** — the memory that makes next week cheap.

---

## Part 7 — Failure modes and the guardrails against them

**Usage caps mid-run.** Already hit twice. Mitigated by workflow resumability — completed agents replay from cache, so a resumed run costs only what did not finish — plus phase-level state checkpointing and cheap models on the mechanical bulk.

**Recommending a player who is not actually available.** The most damaging possible failure, because it looks authoritative and wastes a claim. Hard gate: every recommended name must be validated against the Sleeper roster data confirming he is genuinely a free agent *in this league* before it reaches the output. No exceptions, and this check belongs in deterministic code, not in a prompt.

**Stale news presented as current.** Injury and role claims must cite a source dated within roughly seven days, and every claim carries a timestamp. The draft-prep sweep produced one section built on Wikipedia rather than live beat coverage and it had to be redone — the lesson is to require freshness explicitly rather than hoping for it.

**Context loss between sessions.** The state files are canonical, not the chat. The skill rehydrates from them, so a brand-new conversation is fully functional as long as the files exist. Files should be delivered to you each week so you hold a copy independent of any container.

**Overreacting to noise.** Explicit small-sample rules in the early weeks, and the `decisions_log` grading its own past calls to catch a heuristic that keeps missing.

**Sleeper API drift.** The deterministic layer is deliberately thin and isolated, so a schema change breaks one small module rather than the whole system.

---

## Part 8 — Build roadmap

Sequenced so that each phase is independently useful, and so nothing is wasted if you stop after any step.

**Phase 1 — Foundation (before Week 1).** Write `league_config.json` from the reference doc that already exists. Build and test `sync_sleeper.py` against the live league through WebFetch. Start the incremental `players_cache.json`, which immediately resolves the unidentified bench players on several rosters. Deliverable: a script that prints an accurate current picture of the league on demand.

**Phase 2 — Skeleton run (Week 1).** Build `weekly.js` with only the deterministic sync plus a single synthesis agent. No opponent modelling yet. Deliverable: a real, if shallow, Tuesday brief — and confirmation the plumbing works end to end.

**Phase 3 — Intelligence (Weeks 2–3).** Add the nine opponent agents and the four news agents. Add the free-agent pool ranking. Deliverable: the opponent intel brief and a genuine waiver claim sheet.

**Phase 4 — Judgment (Weeks 3–4).** Add the opus contention model and the trade board. Deliverable: ordered claims with real probabilities, and sendable trade offers.

**Phase 5 — Packaging (Week 4–5).** Wrap it all in the `sunday-scaries` skill so it survives a fresh chat and runs from one command. Deliverable: `/tuesday` works from a cold start.

**Phase 6 — Automation (Week 5+).** Optional scheduled task that fires Tuesday morning so the brief is waiting. Add the keeper-equity board and season-phase logic.

---

## Open questions to resolve before Phase 1

1. **Waiver type.** The commissioner's notes say reverse-standings rolling priority, but Sleeper's settings also carry a hundred-unit waiver budget field, which usually indicates FAAB. These imply completely different claim strategies — priority ordering versus bid sizing — so the contention model cannot be built correctly until this is confirmed.
2. **Waiver processing day.** Sleeper shows day-of-week 2 with a two-day clear, which needs pinning to an actual clock time so the Tuesday run lands before claims process rather than after.
3. **The FLEX count**, still unresolved from draft prep — Sleeper shows two FLEX slots, the rules document says one. This changes both lineup optimisation and positional valuation.
4. **Defence scoring**, flagged by the commissioner as being fixed but not yet confirmed as applied.
