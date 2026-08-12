#!/usr/bin/env python3
"""
build_analysis_output.py -- Phase 3 glue: run the deterministic analysis stack
against a state file BEFORE weekly.js's Workflow ever starts, and write one
combined system/state/week_N_analysis_output.json for the workflow to read.

Why this exists
----------------
weekly.js's agent() calls are LLM calls, not code execution -- there is no way
for a prompt mid-workflow to "call" opponent_pressure.py, waiver_contention.py
or keeper_equity.py. The only place those modules can run is before the
Workflow starts, in plain Python, against files already on disk. This script
is that place. Its output gets threaded into weekly.js's prompts as a fixed
string (see weekly_README.md's "baseline vs refine" contract): the LLM agents
cite and REFINE this JSON with qualitative signals (snap counts, beat
reports), they do not recompute it from scratch, and they must not contradict
verified_free_agents' availability flags.

What it does, in order
-----------------------
  1. Load the state file (system/state/week_N.json).
  2. opponent_pressure.compute_league_pressure(state, exclude_andrew=True) --
     one pressure block per rival. No role_signals are supplied at this
     stage (the news agents haven't run yet); the module renormalises its
     weights gracefully over whatever components have data, which is
     documented behaviour in opponent_pressure.py, not a workaround here.
     recent_scoring is pulled from up to 3 prior week_N.json files on disk
     via recent_scoring_from_states(), when they exist.
  3. Build a deterministic free-agent pool straight from
     state['free_agents']['confirmed_available_known_players'] plus
     ['available_defenses'] -- this pool has no individual projections yet
     (week 0 has none), so every player is valued at his position's
     REPLACEMENT_PPG as a first-pass placeholder. This is explicitly a
     placeholder, not a ranking, and is labelled as such in the output.
  4. For each rival, opponent_pressure.predicted_claims_from_pressure(block,
     pool) turns that team's pressure profile into a first-pass predicted
     claims list against the real pool -- the existing glue function built
     for exactly this purpose.
  5. Those predicted claims become rival_claims for
     waiver_contention.contention_report(), which also takes the FULL free
     agent pool as `targets` (every entry pre-flagged
     availability_verified=True, because this pool is already the
     code-verified gate) and returns real Monte-Carlo landing probabilities
     for every one of them against Andrew's actual waiver position.
  6. keeper_equity.build_keeper_board() runs against
     keeper_equity.andrew_roster_from_config(), which already reads
     league_config.json's real 2026 keeper-cost board (computed from the
     real 2025 draft) -- no re-derivation here, just the existing loader.
  7. verified_free_agents is state['free_agents'] passed through unmodified,
     plus the valued pool built in step 3, so agents never have to go
     hunting for the raw section themselves.

Output
------
One JSON file: system/state/week_N_analysis_output.json (N taken from the
state file's meta.week, overridable with --out). Top-level keys:
  _note                 the "deterministic baseline, LLM refines" contract
  meta                  where this came from and when
  opponent_pressure     per-rival pressure blocks, keyed by roster_id (str)
  predicted_claims      per-rival first-pass predicted claims, keyed by owner
  waiver_contention      CONTENTION_SCHEMA-shaped Monte Carlo report
  keeper_equity          ranked keeper board + optimal 3-keeper slate
  verified_free_agents   the code-verified availability gate, pass-through
                         plus the valued pool used above

Pure stdlib. Run directly:
    python3 build_analysis_output.py system/state/week_0.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import opponent_pressure as op  # noqa: E402
import waiver_contention as wc  # noqa: E402
import keeper_equity as ke  # noqa: E402
from scoring import REPLACEMENT_PPG  # noqa: E402

BASELINE_NOTE = (
    "DETERMINISTIC BASELINE. Every number in this file was computed from box-score "
    "and roster data alone (state_builder.py's Sleeper payloads, league_config.json's "
    "keeper-cost board) with no qualitative input -- no snap counts, no beat reports, "
    "no role signals, because those only exist in the news agents that run AFTER this "
    "file is built. The LLM agents' job is to REFINE this with qualitative info they "
    "find, citing it explicitly, not to recompute these numbers from scratch. In "
    "particular: do not contradict verified_free_agents' availability flags -- that is "
    "a hard, code-verified gate, not a starting guess."
)


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Step 3 -- deterministic free-agent pool with placeholder values
# --------------------------------------------------------------------------

def build_free_agent_pool(state):
    """state['free_agents'] -> [{"player","player_id","position","nfl_team","value",...}]

    `value` is REPLACEMENT_PPG for the player's position -- a placeholder, NOT a
    projection. This is a first pass so pressure-vs-pool matching and the
    contention model have something numeric to run on; it does not
    differentiate within a position, and the output says so explicitly so no
    downstream consumer mistakes it for a real ranking.
    """
    fa = state.get("free_agents") or {}
    known = fa.get("confirmed_available_known_players") or []
    defenses = fa.get("available_defenses") or []

    pool = []
    for p in known:
        pos = (p.get("pos") or "").upper()
        pool.append({
            "player": p.get("name"),
            "player_id": p.get("player_id"),
            "position": pos,
            "nfl_team": p.get("team"),
            "value": REPLACEMENT_PPG.get(pos, 10.0),
            "value_basis": "positional replacement-level placeholder (REPLACEMENT_PPG) "
                           "- no individual projection exists yet at this stage",
            "availability_verified": True,
            "available": True,
        })
    for d in defenses:
        pool.append({
            "player": d,
            "player_id": d,
            "position": "DEF",
            "nfl_team": d,
            "value": REPLACEMENT_PPG.get("DEF", 6.0),
            "value_basis": "positional replacement-level placeholder (REPLACEMENT_PPG)",
            "availability_verified": True,
            "available": True,
        })
    return pool


# --------------------------------------------------------------------------
# Priority order / Andrew identity, straight off the state file
# --------------------------------------------------------------------------

def priority_order_from_state(state):
    """[owner, owner, ...] worst record / highest waiver priority first, as
    waiver_contention.py expects it. Falls back to teams_picking_ahead_of_andrew
    plus andrew if waiver_order is missing."""
    order_rows = state.get("waiver_order") or []
    if order_rows:
        rows = sorted(order_rows, key=lambda r: r.get("waiver_priority", 999))
        return [r.get("owner") for r in rows if r.get("owner")]
    # degrade gracefully rather than crash
    ahead = state.get("teams_picking_ahead_of_andrew") or []
    andrew = andrew_owner_from_state(state)
    return list(ahead) + ([andrew] if andrew else [])


def andrew_owner_from_state(state):
    for team in (state.get("teams") or {}).values():
        if team.get("is_andrew"):
            return team.get("owner")
    for row in state.get("standings") or []:
        if row.get("is_andrew"):
            return row.get("owner")
    return "andrewroth32"


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build(state, state_path):
    week = (state.get("meta") or {}).get("week")
    if week is None:
        week = 0

    state_dir = os.path.dirname(os.path.abspath(state_path))
    recent_scoring, recent_notes = op.recent_scoring_from_states(state_dir, int(week))

    # Step 2 -- league-wide pressure, excluding Andrew, no role_signals supplied
    # at this stage on purpose (news agents haven't run yet).
    pressure_by_roster = op.compute_league_pressure(
        state, recent_scoring=recent_scoring, exclude_andrew=True)

    # Step 3 -- the deterministic FA pool
    fa_pool = build_free_agent_pool(state)

    # Step 4 -- per-rival first-pass predicted claims against the real pool
    predicted_claims_by_owner = {}
    for rid, block in pressure_by_roster.items():
        owner = block.get("owner") or rid
        predicted_claims_by_owner[owner] = op.predicted_claims_from_pressure(
            block, fa_pool, top_n=3, min_pressure=0.25)

    # Step 5 -- Monte Carlo waiver contention over the whole verified pool
    priority_order = priority_order_from_state(state)
    andrew = andrew_owner_from_state(state)
    andrew_priority = state.get("andrew_waiver_position")
    waiver_meta = (state.get("meta") or {}).get("waiver") or {}
    mode = "faab" if waiver_meta.get("is_faab") else "rolling_priority"

    targets = [dict(p) for p in fa_pool]  # already availability_verified=True
    contention = wc.contention_report(
        targets,
        priority_order=priority_order,
        rival_claims=predicted_claims_by_owner,
        andrew=andrew,
        andrew_priority=andrew_priority,
        mode=mode,
        roster_spots_open=0,
        require_availability=True,
    )

    # Step 6 -- keeper equity off the real 2026 keeper-cost board
    andrew_players = ke.andrew_roster_from_config(season=2026)
    keeper_board = ke.build_keeper_board(andrew_players, season=2026)
    keeper_slate = ke.optimal_keeper_slate(andrew_players, season=2026)

    out = {
        "_note": BASELINE_NOTE,
        "meta": {
            "generator": "build_analysis_output.py",
            "generated_at": _now_iso(),
            "source_state": os.path.abspath(state_path),
            "week": week,
            "recent_scoring_notes": recent_notes,
            "role_signals_supplied": False,
            "waiver_mode_used": mode,
        },
        "opponent_pressure": pressure_by_roster,
        "predicted_claims": predicted_claims_by_owner,
        "waiver_contention": contention,
        "keeper_equity": {
            "board": keeper_board,
            "optimal_slate": keeper_slate,
        },
        "verified_free_agents": {
            "raw": state.get("free_agents") or {},
            "valued_pool": fa_pool,
        },
    }
    return out


def default_out_path(state_path, week):
    state_dir = os.path.dirname(os.path.abspath(state_path))
    return os.path.join(state_dir, "week_%s_analysis_output.json" % week)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        here = os.path.dirname(os.path.abspath(__file__))
        state_path = os.path.join(here, "..", "state", "week_0.json")
    else:
        state_path = argv[0]

    out_path = None
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]

    state = load_state(state_path)
    result = build(state, state_path)

    if out_path is None:
        out_path = default_out_path(state_path, result["meta"]["week"])

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=False)
        fh.write("\n")

    print("wrote %s (%s bytes)" % (out_path, format(os.path.getsize(out_path), ",")),
          file=sys.stderr)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
