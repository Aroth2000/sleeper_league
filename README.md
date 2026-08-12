# sleeper_league

This is the git-backed home for Andrew's Sunday Scaries fantasy football management
system (Sleeper, 10-team superflex half-PPR-plus-first-down keeper league).

Start here: **`system/skill/SKILL.md`** — the operational runbook for the weekly
Tuesday run (lineup, waiver claims, drop candidates, trade offers, opponent intel).

## Layout

```
system/            the full operational system: state builder, merge logic,
                    deterministic analysis modules, the weekly agent workflow,
                    the players cache, and the skill runbook.
data/week_NN/       the weekly archive. Each week's finalized state snapshot
                    lives at data/week_NN/state.json, going forward from
                    data/week_00/state.json (the preseason baseline).
```

`data/week_NN/` is append-only history: once a week's run closes, its state
snapshot is committed here so the league's full season is reconstructible from
git history alone, independent of the sandbox's local filesystem.
