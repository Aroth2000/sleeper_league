#!/usr/bin/env python3
"""
opponent_pressure.py -- Part 4 of the weekly plan, made deterministic.

The idea in one sentence: *a manager whose starter just got hurt, benched, or
quietly lost his job is about to hit the waiver wire*, and if we can score that
before he does, we know which claims will be contested.

Four distinct pressures, exactly as specified in the plan:

  vacancy      A starter is out / doubtful / suspended / on bye. Highest signal,
               comes straight from the Sleeper injury field plus the schedule.
  performance  A starter is producing below replacement over a rolling 2-3 week
               window. Factual, computed from /matchups scoring.
  role         A player is losing snaps, routes or targets BEFORE the box score
               reflects it. This CANNOT be derived from Sleeper data -- it only
               exists in beat reporting and snap counts, so it is accepted as an
               EXTERNAL INPUT from the news agents. Never invented here.
  depth        No viable replacement on their own bench, so the fix has to come
               from outside. This is the multiplier that converts "something is
               wrong" into "they will make a move".

Combination model
-----------------
    need     = w_v*vacancy + w_p*performance + w_r*role          (weights sum to 1)
    pressure = need * (INTERNAL_FLOOR + (1-INTERNAL_FLOOR)*depth) * ACTION_MULT[pos]

Weights are renormalised over only the components that actually have data. A
missing role report means the news agents have not covered that team this week;
it does NOT mean role pressure is zero, and scoring it as zero would quietly
flatten every team into "settled" on a thin news week.

`need` says the position is broken. `depth` says they cannot fix it internally.
A team with a hurt RB1 and a good handcuff on the bench has high need but low
external pressure -- they plug it in-house and never touch the wire. That
distinction is the whole point of the depth term, and it is why depth is applied
multiplicatively rather than as a fourth addend.

INTERNAL_FLOOR = 0.35 because even a team with perfect bench cover often adds a
body anyway; pressure never collapses to zero on need alone.

Public API
----------
    compute_position_pressure(...)              -> one PressureRow dict
    compute_team_pressure(team, ...)            -> OPPONENT_SCHEMA-shaped block
    compute_league_pressure(state, ...)         -> {roster_id: block}
    predicted_claims_from_pressure(block, pool) -> [{player, position, likelihood, why}]
    rank_positions_by_pressure(block)           -> [(pos, score), ...]

Output is shaped to drop straight into weekly.js's OPPONENT_SCHEMA
(`pressure`, `pressure_breakdown`, `need_positions`, `surplus_positions`,
`vulnerable_starters`, `predicted_claims`, `confidence`, `data_gaps`).

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

try:  # works imported as a package member or as a loose script
    from .scoring import REPLACEMENT_PPG
except ImportError:  # pragma: no cover - exercised by direct execution
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scoring import REPLACEMENT_PPG

__all__ = [
    "PRESSURE_WEIGHTS",
    "INTERNAL_FLOOR",
    "ACTION_MULTIPLIER",
    "INJURY_SEVERITY",
    "FLEX_CROSS_COVER",
    "SCORABLE_POSITIONS",
    "injury_severity",
    "vacancy_pressure",
    "performance_pressure",
    "depth_pressure",
    "compute_position_pressure",
    "compute_team_pressure",
    "compute_league_pressure",
    "rank_positions_by_pressure",
    "predicted_claims_from_pressure",
]

# --------------------------------------------------------------------------
# Calibration constants. All overridable via compute_* kwargs so a future week
# can re-tune from observed behaviour without editing the module.
# --------------------------------------------------------------------------

PRESSURE_WEIGHTS = {
    "vacancy": 0.42,      # loudest and most reliable
    "performance": 0.22,  # real but noisy, and slow
    "role": 0.36,         # the edge: it leads the box score by a week
}

INTERNAL_FLOOR = 0.35
FLEX_CROSS_COVER = 0.45   # a bench WR covers an RB hole only via the FLEX slot

# DEF is trivially streamable, so a DEF hole is real but produces a cheap,
# low-contention claim. TE slightly discounted for the same reason.
ACTION_MULTIPLIER = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 0.95, "DEF": 0.8, "K": 0.6}

SCORABLE_POSITIONS = ["QB", "RB", "WR", "TE", "DEF"]

# Sleeper injury_status strings -> how much of the starter is actually gone.
INJURY_SEVERITY = {
    "IR": 1.0,
    "INJURED RESERVE": 1.0,
    "OUT": 1.0,
    "SUS": 1.0,
    "SUSP": 1.0,
    "SUSPENDED": 1.0,
    "DNR": 1.0,
    "NA": 0.9,
    "PUP": 0.9,
    "DOUBTFUL": 0.8,
    "COV": 0.5,
    "DTD": 0.35,
    "QUESTIONABLE": 0.35,
    "LIMITED": 0.25,
    "PROBABLE": 0.1,
    "HEALTHY": 0.0,
    "ACTIVE": 0.0,
}

BYE_SEVERITY = 0.9  # a bye is a guaranteed one-week hole; managers absolutely act

# How many bodies a team wants at each position given QB/RB/RB/WR/WR/TE/FLEX/
# FLEX/SUPER_FLEX/DEF. Used to decide how deep the bench has to be before the
# position counts as covered.
STARTER_DEMAND = {"QB": 2, "RB": 2, "WR": 2, "TE": 1, "DEF": 1}

FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SUPERFLEX_ELIGIBLE = {"QB", "RB", "WR", "TE"}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(x)))


def _noisy_or(values):
    """Combine independent-ish signals so two half-problems beat one whole one
    without ever exceeding 1.0."""
    prod = 1.0
    for v in values:
        prod *= (1.0 - _clamp(v))
    return 1.0 - prod


# --------------------------------------------------------------------------
# Component 1 -- vacancy
# --------------------------------------------------------------------------

def injury_severity(status):
    """Map a Sleeper injury_status string to 0..1. Unknown non-empty strings are
    treated as 0.5 rather than 0, because an unrecognised flag is still a flag."""
    if status is None:
        return 0.0
    key = str(status).strip().upper()
    if not key or key in ("NONE", "NULL"):
        return 0.0
    return INJURY_SEVERITY.get(key, 0.5)


def vacancy_pressure(starters_at_pos, bye_player_ids=None):
    """How much of this team's starting production at a position is missing.

    starters_at_pos: [{player_id, name, injury_status, on_bye?}, ...]
    """
    bye_player_ids = set(bye_player_ids or [])
    hits = []
    evidence = []
    for p in starters_at_pos:
        sev = injury_severity(p.get("injury_status"))
        if sev:
            evidence.append("%s %s" % (p.get("name") or p.get("player_id"), p.get("injury_status")))
        if p.get("on_bye") or p.get("player_id") in bye_player_ids:
            if BYE_SEVERITY > sev:
                sev = BYE_SEVERITY
                evidence.append("%s on bye" % (p.get("name") or p.get("player_id")))
        if sev:
            hits.append(sev)
    if not starters_at_pos:
        # A slot they are supposed to fill with nobody in it at all is a total
        # vacancy -- rarer than it sounds, but it happens after a drop.
        return 1.0, ["no starter rostered at this position"]
    return _noisy_or(hits), evidence


# --------------------------------------------------------------------------
# Component 2 -- performance
# --------------------------------------------------------------------------

def _ppg(recent, player_id, window=3):
    """Recent points per game for a player.

    Accepts either {pid: [12.1, 8.4, ...]} (most recent LAST) or
    {pid: {"5": 12.1, "6": 8.4}} keyed by week. Returns (ppg, n_games)."""
    if not recent or player_id not in recent:
        return None, 0
    val = recent[player_id]
    if isinstance(val, dict):
        weeks = sorted(val.keys(), key=lambda k: int(k))
        vals = [float(val[w]) for w in weeks if val[w] is not None]
    elif isinstance(val, (int, float)):
        return float(val), 1
    else:
        vals = [float(v) for v in val if v is not None]
    vals = vals[-window:]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def performance_pressure(starters_at_pos, recent_scoring, position, window=3,
                         week=None, replacement=None):
    """How far below replacement level this team's starters are running.

    Injured/absent starters are EXCLUDED -- their damage is already counted as
    vacancy, and counting their zeroes here would double-charge the same hole.

    Small-sample discipline (plan, Part 5): through week 3 the whole component
    is damped, because a two-game slump is not evidence.
    """
    repl = (replacement or REPLACEMENT_PPG).get(position, 10.0)
    if not repl:
        return 0.0, [], 0
    shortfalls = []
    evidence = []
    n_total = 0
    for p in starters_at_pos:
        if injury_severity(p.get("injury_status")) >= 0.8 or p.get("on_bye"):
            continue
        ppg, n = _ppg(recent_scoring, p.get("player_id"), window=window)
        if ppg is None:
            continue
        n_total = max(n_total, n)
        short = _clamp((repl - ppg) / repl)
        # confidence in the sample itself
        short *= min(1.0, n / 3.0)
        shortfalls.append(short)
        if short > 0.2:
            evidence.append("%s %.1f ppg vs %.1f replacement over %d wk" % (
                p.get("name") or p.get("player_id"), ppg, repl, n))
    if not shortfalls:
        return 0.0, [], 0
    worst = max(shortfalls)
    mean = sum(shortfalls) / len(shortfalls)
    score = 0.65 * worst + 0.35 * mean
    if week is not None and week <= 3:
        score *= 0.6
        evidence.append("damped: week %s is small-sample territory" % week)
    return _clamp(score), evidence, n_total


# --------------------------------------------------------------------------
# Component 3 -- role (external input only)
# --------------------------------------------------------------------------

def _role_signal(role_signals, position, starters_at_pos):
    """Role pressure is supplied by the news agents, never derived here.

    Accepts {"RB": 0.7} or {player_id: 0.7} or
            {"RB": {"score": 0.7, "evidence": "..."}} or a list of
            [{"position"/"player_id", "score", "evidence"}].
    """
    if not role_signals:
        return 0.0, [], False

    def _unpack(v):
        if isinstance(v, dict):
            return float(v.get("score", v.get("value", 0.0))), v.get("evidence")
        return float(v), None

    scores = []
    evidence = []
    if isinstance(role_signals, list):
        table = {}
        for item in role_signals:
            key = item.get("player_id") or item.get("position")
            if key is not None:
                table[key] = item
        role_signals = table

    if position in role_signals:
        s, ev = _unpack(role_signals[position])
        scores.append(s)
        if ev:
            evidence.append(ev)
    for p in starters_at_pos:
        pid = p.get("player_id")
        if pid in role_signals:
            s, ev = _unpack(role_signals[pid])
            scores.append(s)
            evidence.append(ev or "role signal on %s" % (p.get("name") or pid))
    if not scores:
        return 0.0, [], False
    return _clamp(_noisy_or(scores)), [e for e in evidence if e], True


# --------------------------------------------------------------------------
# Component 4 -- depth
# --------------------------------------------------------------------------

def depth_pressure(position, bench, recent_scoring=None, window=3,
                   replacement=None, unknown_bench_viability=0.45):
    """1.0 = nothing on their bench can cover this, so they MUST go outside.

    Cross-cover: a bench WR does partially cover an RB hole, because the hole
    can be absorbed at FLEX. Counted at FLEX_CROSS_COVER weight. In SUPERFLEX a
    bench QB is a genuine asset for the SUPER_FLEX slot, so QB cross-cover runs
    the same way.
    """
    repl = (replacement or REPLACEMENT_PPG).get(position, 10.0)
    viabilities = []
    evidence = []
    unknown_used = False
    for p in bench or []:
        pos = (p.get("pos") or p.get("position") or "").upper()
        if pos == position:
            weight = 1.0
        elif position in FLEX_ELIGIBLE and pos in FLEX_ELIGIBLE:
            weight = FLEX_CROSS_COVER
        elif position == "QB" and pos in SUPERFLEX_ELIGIBLE:
            weight = FLEX_CROSS_COVER if pos != "QB" else 1.0
        else:
            continue
        sev = injury_severity(p.get("injury_status"))
        if sev >= 0.8 or p.get("on_bye"):
            continue  # a hurt backup is not cover
        ppg, n = _ppg(recent_scoring, p.get("player_id"), window=window)
        if ppg is None:
            v = unknown_bench_viability
            unknown_used = True
        else:
            v = _clamp(ppg / repl) if repl else 0.0
            v *= min(1.0, max(n, 1) / 3.0) + (1 - min(1.0, max(n, 1) / 3.0)) * 0.7
        v *= weight * (1.0 - sev)
        if v > 0:
            viabilities.append(v)
            if weight == 1.0:
                evidence.append("%s on bench" % (p.get("name") or p.get("player_id")))
    if not viabilities:
        return 1.0, ["no bench cover at %s" % position], unknown_used
    best = max(viabilities)
    # A second usable body meaningfully reduces urgency, but far less than the first.
    second = sorted(viabilities, reverse=True)[1] if len(viabilities) > 1 else 0.0
    cover = _clamp(best + 0.25 * second)
    return _clamp(1.0 - cover), evidence, unknown_used


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def compute_position_pressure(position, starters_at_pos, bench, recent_scoring=None,
                              role_signals=None, bye_player_ids=None, week=None,
                              weights=None, window=3, replacement=None,
                              action_multiplier=None, internal_floor=INTERNAL_FLOOR):
    """Score one position for one team. Returns a pressure_breakdown row."""
    w = dict(PRESSURE_WEIGHTS)
    if weights:
        w.update(weights)
    total_w = sum(w.values()) or 1.0

    vac, vac_ev = vacancy_pressure(starters_at_pos, bye_player_ids)
    perf, perf_ev, n_games = performance_pressure(
        starters_at_pos, recent_scoring, position, window=window, week=week,
        replacement=replacement)
    role, role_ev, role_supplied = _role_signal(role_signals, position, starters_at_pos)
    depth, depth_ev, depth_unknown = depth_pressure(
        position, bench, recent_scoring=recent_scoring, window=window,
        replacement=replacement)

    # Renormalise over the components that actually have data behind them.
    # A missing role report is NOT evidence that role pressure is zero -- it means
    # the news agents have not covered this team yet. Scoring it as a hard zero
    # would drag a genuinely desperate team down toward "settled", which is the
    # exact failure that matters: a rival with a dead RB1 and a bare bench must
    # read as high pressure even in a week when no beat reporting came back.
    supplied = [("vacancy", vac, True),
                ("performance", perf, n_games > 0),
                ("role", role, role_supplied)]
    num = sum(w[k] * v for k, v, ok in supplied if ok)
    den = sum(w[k] for k, _, ok in supplied if ok) or total_w
    need = num / den
    mult = (action_multiplier or ACTION_MULTIPLIER).get(position, 1.0)
    pressure = _clamp(need * (internal_floor + (1 - internal_floor) * depth) * mult)

    gaps = []
    if not recent_scoring:
        gaps.append("no recent scoring supplied - performance and depth are estimates")
    elif n_games == 0:
        gaps.append("no scoring history for any %s starter" % position)
    if not role_supplied:
        gaps.append("no role signal supplied for %s - news agents have not reported" % position)
    if depth_unknown:
        gaps.append("bench viability at %s assumed, not measured" % position)

    evidence = "; ".join([e for e in (vac_ev + perf_ev + role_ev + depth_ev) if e]) or "nothing flagged"
    return {
        "position": position,
        "vacancy": round(vac, 3),
        "performance": round(perf, 3),
        "role": round(role, 3),
        "depth": round(depth, 3),
        "need": round(need, 3),
        "pressure": round(pressure, 3),
        "evidence": evidence,
        "components_used": [k for k, _, ok in supplied if ok],
        "role_signal_supplied": role_supplied,
        "data_gaps": gaps,
    }


def _starters_by_pos(team):
    """Group a state-file team block's starters by position, tolerating both the
    rich `starters` list of dicts and a bare `starter_ids` list."""
    out = {}
    for p in team.get("starters") or []:
        pos = (p.get("pos") or p.get("position") or "").upper()
        out.setdefault(pos, []).append(p)
    return out


def compute_team_pressure(team, recent_scoring=None, role_signals=None,
                          bye_player_ids=None, week=None, positions=None,
                          need_threshold=0.5, surplus_threshold=0.22, **kwargs):
    """Full per-team pressure block, shaped for weekly.js's OPPONENT_SCHEMA.

    `team` is a state-file team block: {roster_id, owner, team_name, starters:[...],
    bench:[...]}. `role_signals` comes from the news agents and is never invented.
    """
    positions = positions or SCORABLE_POSITIONS
    by_pos = _starters_by_pos(team)
    bench = team.get("bench") or []

    rows = []
    for pos in positions:
        rows.append(compute_position_pressure(
            pos, by_pos.get(pos, []), bench, recent_scoring=recent_scoring,
            role_signals=role_signals, bye_player_ids=bye_player_ids, week=week,
            **kwargs))

    pressure = {r["position"]: r["pressure"] for r in rows}
    need = [r["position"] for r in sorted(rows, key=lambda r: -r["pressure"])
            if r["pressure"] >= need_threshold]
    surplus = [r["position"] for r in rows
               if r["pressure"] <= surplus_threshold and r["depth"] <= 0.35
               and r["vacancy"] < 0.3]

    vulnerable = []
    for pos, plist in by_pos.items():
        prow = next((r for r in rows if r["position"] == pos), None)
        if not prow:
            continue
        for p in plist:
            sev = injury_severity(p.get("injury_status"))
            ppg, n = _ppg(recent_scoring, p.get("player_id"), window=kwargs.get("window", 3))
            under = ppg is not None and ppg < REPLACEMENT_PPG.get(pos, 10.0)
            if sev >= 0.35 or under or (prow["role"] >= 0.5):
                vulnerable.append(p.get("name") or p.get("player_id"))

    gaps = sorted({g for r in rows for g in r["data_gaps"]})
    # Confidence is about how much of the model ran on real data, not about how
    # confident the numbers feel.
    have_scoring = bool(recent_scoring)
    have_role = any(r["role_signal_supplied"] for r in rows)
    if have_scoring and have_role:
        confidence = "high"
    elif have_scoring or have_role:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "roster_id": team.get("roster_id"),
        "owner": team.get("owner"),
        "team": team.get("team_name") or team.get("owner"),
        "waiver_priority": team.get("waiver_priority", -1),
        "pressure": pressure,
        "pressure_breakdown": rows,
        "need_positions": need,
        "surplus_positions": surplus,
        "vulnerable_starters": sorted(set(vulnerable)),
        "confidence": confidence,
        "data_gaps": gaps,
    }


def compute_league_pressure(state, recent_scoring=None, role_signals=None,
                            bye_player_ids=None, exclude_andrew=False, **kwargs):
    """Run every team in a state-file. `role_signals` may be keyed by roster_id.

    Returns {roster_id_str: block}, ready to be written into state.opponent_model.
    """
    week = kwargs.pop("week", None)
    if week is None:
        week = (state.get("meta") or {}).get("week")
    out = {}
    for rid, team in (state.get("teams") or {}).items():
        if exclude_andrew and team.get("is_andrew"):
            continue
        rs = role_signals or {}
        team_roles = rs.get(str(rid), rs.get(int(rid) if str(rid).isdigit() else rid, rs))
        # If the caller passed a flat signal table (position-keyed), reuse it.
        out[str(rid)] = compute_team_pressure(
            team, recent_scoring=recent_scoring, role_signals=team_roles,
            bye_player_ids=bye_player_ids, week=week, **kwargs)
    return out


def rank_positions_by_pressure(block):
    return sorted(block["pressure"].items(), key=lambda kv: -kv[1])


def predicted_claims_from_pressure(block, free_agent_pool, top_n=3,
                                   min_pressure=0.25, value_key="value"):
    """Turn a pressure block plus a ranked FA pool into predicted claims.

    This is the glue into waiver_contention: likelihood that THIS team claims
    THIS player = positional pressure * how much better the FA is than what a
    replacement-level body would give them.

    free_agent_pool: [{"player","position","value"(league ppg or 0-100 score)}]
    """
    ranked = []
    for fa in free_agent_pool or []:
        pos = (fa.get("position") or fa.get("pos") or "").upper()
        press = block["pressure"].get(pos, 0.0)
        if press < min_pressure:
            continue
        val = float(fa.get(value_key, fa.get("value", 0.0)) or 0.0)
        ranked.append((val, pos, press, fa))
    if not ranked:
        return []
    top_val = max(r[0] for r in ranked) or 1.0
    claims = []
    for val, pos, press, fa in ranked:
        quality = _clamp(val / top_val)
        likelihood = round(_clamp(press * (0.45 + 0.55 * quality)), 3)
        claims.append({
            "player": fa.get("player") or fa.get("name"),
            "position": pos,
            "likelihood": likelihood,
            "why": "%s pressure %.2f at %s; FA value %.1f" % (
                block.get("owner") or "team", press, pos, val),
        })
    claims.sort(key=lambda c: -c["likelihood"])
    return claims[:top_n]


# --------------------------------------------------------------------------
# CLI: read a state file (or a {team, recent_scoring, role_signals} payload)
# --------------------------------------------------------------------------

def recent_scoring_from_states(state_dir, week, window=3):
    """Build the {player_id: [wk-2, wk-1, wk]} dict that performance_pressure and
    depth_pressure need, by reading the last `window` weekly state files.

    Without this, `recent_scoring` had no producer anywhere in the system, so
    PERFORMANCE and DEPTH pressure -- two of the four pressures the plan's Part 4
    requires -- silently evaluated to 0/estimated on every single team, every week,
    and the deterministic model was a vacancy detector wearing a four-pressure label.

    Reads state/week_N.json -> matchups.by_roster[*].starters/bench_points, which is
    where state_builder.py lands the per-player points from /matchups. Missing weeks
    are skipped, not faked. Returns ({} , [notes]) when nothing is available.
    """
    out, weeks_used, missing = {}, [], []
    for w in range(max(1, week - window + 1), week + 1):
        path = os.path.join(state_dir, "week_%d.json" % w)
        if not os.path.exists(path):
            missing.append(w)
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
        except (OSError, ValueError):
            missing.append(w)
            continue
        by_roster = ((st.get("matchups") or {}).get("by_roster") or {})
        if not by_roster:
            missing.append(w)
            continue
        weeks_used.append(w)
        for blk in by_roster.values():
            for row in (blk.get("starters") or []) + (blk.get("bench_points") or []):
                pid, pts = row.get("player_id"), row.get("points")
                if pid is None or pts is None:
                    continue
                out.setdefault(pid, {})[str(w)] = float(pts)
    notes = []
    if weeks_used:
        notes.append("recent_scoring built from weeks %s (%d players)"
                     % (weeks_used, len(out)))
    else:
        notes.append("no weekly state files with matchup data found -- performance and "
                     "depth pressure will be unmeasured")
    if missing:
        notes.append("no matchup data for week(s) %s" % missing)
    return out, notes


def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    argv = [a for a in raw if not a.startswith("-")]
    if not argv:
        here = os.path.dirname(os.path.abspath(__file__))
        argv = [os.path.join(here, "..", "state", "week_0.json")]
    with open(argv[0]) as fh:
        payload = json.load(fh)
    if "teams" in payload and "meta" in payload:
        recent = None
        if "--with-recent-scoring" in raw:
            wk = (payload.get("meta") or {}).get("week") or 0
            recent, notes = recent_scoring_from_states(
                os.path.dirname(os.path.abspath(argv[0])), int(wk))
            for n in notes:
                print("# " + n, file=sys.stderr)
        out = compute_league_pressure(payload, recent_scoring=recent)
    elif "team" in payload:
        out = compute_team_pressure(
            payload["team"],
            recent_scoring=payload.get("recent_scoring"),
            role_signals=payload.get("role_signals"),
            week=payload.get("week"))
    else:
        out = compute_team_pressure(payload)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
