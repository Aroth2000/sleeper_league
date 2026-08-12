# Season-phase behaviour

The same question deserves a different answer in Week 2 and Week 12. The system derives its phase
from the week — it is never passed in — and changes its own defaults accordingly. `weekly.js`
injects the active phase's rules into every agent prompt, so a Week 2 run and a Week 12 run
genuinely answer the same question differently.

| Phase | Weeks | Default posture |
|---|---|---|
| **preseason** | 0 | Draft prep and keeper decisions. No lineup or waiver activity. Week 0 state is a baseline, not a played week. |
| **small_sample** | 1–3 | Judge **opportunity** — snaps, routes run, target share — **not fantasy points.** Do not cut a good player for a one-week wonder. Claims target opportunity *changes*, not box scores. |
| **trade_window** | 4–8 | The most aggressive phase for the trade board. Rivals have formed strong opinions off small samples, which is exactly when buy-low and sell-high offers land. |
| **playoff_positioning** | 9–13 | Weight **weeks 15–17 schedules** over season-long averages. **Trade deadline is week 13** — a hard wall for any consolidation move; count down to it explicitly. |
| **playoffs** | 14–17 | Streaming and matchup optimisation dominate. Week 14 is the last regular-season week — the last chance to secure a seed. **If elimination becomes likely, flip the entire objective to keeper-equity accumulation for 2027.** |

## How the phase actually changes behaviour

**Weeks 1–3 — the sample-size trap.** Three games of fantasy points is noise; three games of snap
share is signal. In this phase the brief should lead with role and usage, explicitly discount
box-score outliers, and be reluctant about drops. The failure mode is cutting a good player because
of one bad matchup, which is unrecoverable in a 10-team league where the wire is thin.

**Weeks 4–8 — the trade window.** This is the only phase where the trade board should be the loudest
section of the brief. Rival managers are now confident and wrong in both directions. Cross Andrew's
positional surplus against each rival's acute, *sustained* need (see `teams.md` — a team with acute
need where Andrew has surplus will overpay) and draft specific, sendable offers with a one-line
rationale aimed at that owner's actual situation.

**Weeks 9–13 — positioning.** Stop optimising for season-long averages and start optimising for the
three weeks that decide the title. Every brief from week 9 onward should state how many weeks remain
until the deadline. Week 13 is the last week a trade can happen at all.

**Weeks 14–17 — playoffs, or the pivot.** Streaming defences and matchup-based flex calls dominate.
The important branch: once elimination is likely, **the objective changes**. Marginal veteran
upgrades stop being worth anything and every roster spot becomes a bet on a 12th-round 2027 keeper.
Make that pivot explicit in the brief rather than quietly changing the recommendations — Andrew
should know when the system has switched objectives.

## Season-long, all phases

- Reverse-standings priority means a rough start improves waiver position. Patience is rewarded; do
  not burn priority early on a marginal upgrade.
- Only 6 bench spots. Every stash has a real opportunity cost.
- Keeper equity accrues from week 1, not from week 14. Log it as it happens.
