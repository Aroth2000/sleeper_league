#!/usr/bin/env python3
"""
scoring.py -- exact Sunday Scaries league scoring.

Why this module exists
----------------------
Every projection you can find on the internet is priced in standard or half-PPR.
This league is half-PPR **plus 0.5 per first down, rushing and receiving**. That
bonus is not cosmetic: a possession receiver with 6 catches and 5 first downs
gains +2.5 pts/gm over his half-PPR price, while a two-catch deep threat with a
75-yard touchdown gains +0.5. Over a season that is a full tier of positional
value, and it is the single most exploitable quirk of this league.

So: nothing anywhere else in the system is allowed to say "points" without
having come through here first.

Public API
----------
    score_stat_line(stats, scoring=None, position=None) -> float
    score_breakdown(stats, ...)                         -> dict
    half_ppr_points(stats)                              -> float
    first_down_bonus(stats)                             -> float
    estimate_first_downs(stats, position)               -> {"rec_fd":, "rush_fd":}
    league_points_from_half_ppr(pts, position, ...)     -> float
    first_down_premium(position, rec_pg, rush_att_pg)   -> float  (pts/gm added)
    REPLACEMENT_PPG                                     -> dict, this format
    load_scoring(config_path)                           -> dict

CLI
---
    echo '{"stats": {"rec": 7, "rec_yd": 84, "rec_fd": 5}}' | python3 scoring.py
    python3 scoring.py --demo

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

__all__ = [
    "LEAGUE_SCORING",
    "HALF_PPR_SCORING",
    "REPLACEMENT_PPG",
    "FIRST_DOWN_RATES",
    "load_scoring",
    "score_stat_line",
    "score_breakdown",
    "half_ppr_points",
    "first_down_bonus",
    "estimate_first_downs",
    "league_points_from_half_ppr",
    "first_down_premium",
    "def_points_allowed_score",
    "rank_projections",
]

# --------------------------------------------------------------------------
# The scoring table itself. Mirrors GET /v1/league/1389753893356838912
# -> scoring_settings (pulled 2026-08-07) and Section 3 of league_reference.md.
# Keys are deliberately the *Sleeper stat keys*, so a raw Sleeper stat dict can
# be scored by direct key lookup with no translation layer.
# --------------------------------------------------------------------------

LEAGUE_SCORING = {
    # passing
    "pass_yd": 0.04,          # 25 yards = 1 pt
    "pass_td": 4.0,
    "pass_int": -1.0,         # NOTE: -1 here, not the -2 most sites assume
    "pass_2pt": 2.0,
    # rushing
    "rush_yd": 0.1,
    "rush_td": 6.0,
    "rush_fd": 0.5,           # <-- the league quirk
    "rush_2pt": 2.0,
    # receiving
    "rec": 0.5,               # half PPR
    "rec_yd": 0.1,
    "rec_td": 6.0,
    "rec_fd": 0.5,            # <-- the league quirk
    "rec_2pt": 2.0,
    # misc offence
    "fum_lost": -2.0,
    "fum": 0.0,
    "fum_rec_td": 6.0,
    # kicking (present in Sleeper defaults; league does not start a K)
    "xpm": 1.0,
    "xpmiss": -1.0,
    "fgm_0_19": 3.0,
    "fgm_20_29": 3.0,
    "fgm_30_39": 3.0,
    "fgm_40_49": 4.0,
    "fgm_50p": 5.0,
    "fgmiss": -1.0,
    # team defence / special teams
    "sack": 1.0,
    "int": 2.0,
    "def_int": 2.0,
    "fum_rec": 2.0,
    "def_fum_rec": 2.0,
    "ff": 1.0,
    "safe": 2.0,
    "def_td": 6.0,
    "st_td": 6.0,
    "def_st_td": 6.0,
    "blk_kick": 2.0,
    "st_ff": 1.0,
    "st_fum_rec": 1.0,
    "def_st_ff": 1.0,
    "def_st_fum_rec": 1.0,
}

# Points-allowed and yards-allowed buckets are scored from a single raw number,
# so they are handled separately rather than as flat multipliers.
DEF_PTS_ALLOWED_BUCKETS = [
    (0, 0, 10.0),
    (1, 6, 7.0),
    (7, 13, 4.0),
    (14, 20, 1.0),
    (21, 27, 0.0),
    (28, 34, -1.0),
    (35, 10 ** 6, -4.0),
]

DEF_YDS_ALLOWED_BUCKETS = [
    (0, 99, 5.0),
    (100, 199, 3.0),
    (200, 299, 2.0),
    (300, 349, 1.0),
    (350, 399, 0.0),
    (400, 449, -1.0),
    (450, 499, -2.0),
    (500, 549, -3.0),
    (550, 10 ** 6, -5.0),
]

# DEF scoring was flagged by the commissioner as buggy/overpowered in 2025 with a
# fix "TBD". Anything that scores a DEF should surface this.
DEF_SCORING_UNVERIFIED = True
DEF_WARNING = (
    "DEF scoring was flagged overpowered/buggy in 2025 and the commissioner's fix "
    "is unconfirmed. Treat DEF point totals as provisional."
)

# Generic half-PPR, i.e. what the rest of the fantasy internet prices players in.
# Identical to the league table with the two first-down bonuses stripped out.
# (pass_int is left at the league's -1 so the delta isolates the FD bonus alone;
# see league_points_from_half_ppr for the interception adjustment.)
HALF_PPR_SCORING = dict(LEAGUE_SCORING)
HALF_PPR_SCORING["rec_fd"] = 0.0
HALF_PPR_SCORING["rush_fd"] = 0.0

# --------------------------------------------------------------------------
# Replacement level, expressed in THIS format's points per game.
#
# 10 teams, SUPERFLEX, 2 FLEX. Starters consumed league-wide per week:
#   QB  ~15-18 (10 QB slots + most SUPER_FLEX slots)
#   RB  ~28-32 (20 RB slots + most of 20 FLEX slots)
#   WR  ~32-36
#   TE  ~12-14
# Replacement is the ppg of the *worst weekly starter* at each position, inflated
# for the first-down bonus relative to conventional half-PPR baselines.
# These are calibration constants -- override them from live matchup data once a
# few weeks of real scoring exist.
# --------------------------------------------------------------------------

REPLACEMENT_PPG = {
    "QB": 16.5,
    "RB": 10.0,
    "WR": 10.5,
    "TE": 7.5,
    "DEF": 6.0,
    "K": 7.0,
}

# --------------------------------------------------------------------------
# First-down estimation.
#
# Used when a projection source gives you catches/carries but not first downs
# (which is nearly every source). Rates are per-reception and per-carry, and
# they are the reason a slot receiver and a field-stretcher with identical
# half-PPR projections are NOT worth the same here.
#
# Rough empirical NFL rates, held deliberately coarse:
#   - WR: ~62% of receptions move the chains (aDOT well past the sticks)
#   - TE: ~63% (short but usually on 2nd/3rd-and-medium)
#   - RB receptions: ~38% (checkdowns behind the sticks)
#   - RB carries: ~23.5%; QB carries ~30% (sneaks/scrambles on 3rd down)
# `profile` lets a news agent nudge a specific player: a designated deep threat
# converts a smaller share of a bigger catch, a chain-mover the reverse.
# --------------------------------------------------------------------------

FIRST_DOWN_RATES = {
    "QB": {"rec": 0.55, "rush": 0.30},
    "RB": {"rec": 0.38, "rush": 0.235},
    "WR": {"rec": 0.62, "rush": 0.30},
    "TE": {"rec": 0.63, "rush": 0.30},
    "DEF": {"rec": 0.0, "rush": 0.0},
    "K": {"rec": 0.0, "rush": 0.0},
}

PROFILE_MULTIPLIERS = {
    "possession": 1.12,     # slot/chain-mover, checkdown back, seam TE
    "chain_mover": 1.12,
    "balanced": 1.0,
    None: 1.0,
    "deep_threat": 0.84,    # boom/bust vertical, contested-catch TD merchant
    "td_dependent": 0.88,
    "gadget": 0.92,
}


def load_scoring(config_path=None):
    """Load the scoring table from league_config.json, falling back to the
    module constant. Keeps a single source of truth without a hard dependency
    on another agent's file existing yet."""
    if config_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(here, "..", "league_config.json")
    try:
        with open(config_path, "r") as fh:
            cfg = json.load(fh)
    except (IOError, OSError, ValueError):
        return dict(LEAGUE_SCORING)

    table = dict(LEAGUE_SCORING)
    sc = cfg.get("scoring") or {}
    for key, val in sc.items():
        if key.startswith("_"):
            continue
        if key == "def" and isinstance(val, dict):
            for dkey, dval in val.items():
                if not dkey.startswith("_") and isinstance(dval, (int, float)):
                    table[dkey] = float(dval)
        elif isinstance(val, (int, float)):
            table[key] = float(val)
    return table


# --------------------------------------------------------------------------
# Core scoring
# --------------------------------------------------------------------------

def _bucket_score(value, buckets):
    for lo, hi, pts in buckets:
        if lo <= value <= hi:
            return pts
    return 0.0


def def_points_allowed_score(pts_allowed, yds_allowed=None, scoring=None):
    """Score the bucketed portion of a team-defence line."""
    total = 0.0
    if pts_allowed is not None:
        total += _bucket_score(int(pts_allowed), DEF_PTS_ALLOWED_BUCKETS)
    if yds_allowed is not None:
        total += _bucket_score(int(yds_allowed), DEF_YDS_ALLOWED_BUCKETS)
    return total


def score_breakdown(stats, scoring=None, position=None):
    """Score a stat line and return every non-zero contribution.

    `stats` uses Sleeper stat keys. Unknown keys are ignored (and reported), so
    a schema drift on Sleeper's side degrades to a slightly low score plus a
    loud `unscored` list rather than a crash.
    """
    table = scoring or LEAGUE_SCORING
    contributions = {}
    unscored = []
    total = 0.0

    for key, raw in (stats or {}).items():
        if raw in (None, 0, 0.0):
            continue
        if key in ("pts_allow", "yds_allow", "player_id", "name", "position", "profile"):
            continue
        if key in table:
            try:
                pts = float(raw) * float(table[key])
            except (TypeError, ValueError):
                unscored.append(key)
                continue
            if pts:
                contributions[key] = round(pts, 4)
                total += pts
        else:
            unscored.append(key)

    pos = (position or (stats or {}).get("position") or "").upper()
    warnings = []
    if "pts_allow" in (stats or {}) or "yds_allow" in (stats or {}):
        bucket = def_points_allowed_score(
            (stats or {}).get("pts_allow"), (stats or {}).get("yds_allow")
        )
        if bucket:
            contributions["pts_yds_allowed_buckets"] = round(bucket, 4)
            total += bucket
    if pos == "DEF" and DEF_SCORING_UNVERIFIED:
        warnings.append(DEF_WARNING)

    fd_pts = first_down_bonus(stats, table)
    return {
        "total": round(total, 3),
        "contributions": contributions,
        "first_down_points": round(fd_pts, 3),
        "half_ppr_equivalent": round(total - fd_pts, 3),
        "first_down_premium": round(fd_pts, 3),
        "unscored_keys": sorted(set(unscored)),
        "warnings": warnings,
    }


def score_stat_line(stats, scoring=None, position=None):
    """League points for one stat line. The only sanctioned way to turn stats
    into points anywhere in this system."""
    return score_breakdown(stats, scoring=scoring, position=position)["total"]


def half_ppr_points(stats, scoring=None):
    """Same line priced in generic half-PPR, for apples-to-apples comparison
    with off-the-shelf rankings."""
    table = dict(scoring or LEAGUE_SCORING)
    table["rec_fd"] = 0.0
    table["rush_fd"] = 0.0
    return score_breakdown(stats, scoring=table)["total"]


def first_down_bonus(stats, scoring=None):
    """Points that exist ONLY because of this league's first-down rule."""
    table = scoring or LEAGUE_SCORING
    total = 0.0
    for key in ("rec_fd", "rush_fd"):
        val = (stats or {}).get(key)
        if val:
            total += float(val) * float(table.get(key, 0.0))
    return total


# --------------------------------------------------------------------------
# Projection conversion
# --------------------------------------------------------------------------

def estimate_first_downs(stats, position, profile=None):
    """Estimate first downs when a projection source does not supply them.

    Prefers explicit rec_fd/rush_fd if already present. Otherwise derives from
    receptions and carries; if neither is present but yardage is, falls back to
    a yards-per-first-down heuristic (~15.5 receiving, ~19 rushing), which is
    coarser and is flagged as such by the caller-visible `method`.
    """
    stats = stats or {}
    pos = (position or stats.get("position") or "WR").upper()
    rates = FIRST_DOWN_RATES.get(pos, FIRST_DOWN_RATES["WR"])
    mult = PROFILE_MULTIPLIERS.get(profile or stats.get("profile"), 1.0)

    method = "explicit"
    rec_fd = stats.get("rec_fd")
    if rec_fd is None:
        rec = stats.get("rec")
        if rec is not None:
            rec_fd = float(rec) * rates["rec"] * mult
            method = "per_reception_rate"
        elif stats.get("rec_yd"):
            rec_fd = float(stats["rec_yd"]) / 15.5 * mult
            method = "yards_fallback"
        else:
            rec_fd = 0.0

    rush_fd = stats.get("rush_fd")
    if rush_fd is None:
        att = stats.get("rush_att")
        if att is not None:
            rush_fd = float(att) * rates["rush"]
            if method == "explicit":
                method = "per_carry_rate"
        elif stats.get("rush_yd"):
            rush_fd = float(stats["rush_yd"]) / 19.0
            if method == "explicit":
                method = "yards_fallback"
        else:
            rush_fd = 0.0

    return {
        "rec_fd": round(float(rec_fd), 2),
        "rush_fd": round(float(rush_fd), 2),
        "method": method,
    }


def league_points_from_half_ppr(
    half_ppr_pts,
    position,
    rec=None,
    rush_att=None,
    rec_yd=None,
    rush_yd=None,
    profile=None,
    source_int_penalty=-2.0,
    pass_int=None,
):
    """Convert an external half-PPR projection into THIS league's points.

    half_ppr_pts : the number the outside world gives you
    rec/rush_att : volume, used to estimate first downs (much better than yards)
    source_int_penalty : most sources price interceptions at -2; this league is
        -1, so a QB projection gains back 1 pt per projected pick. Pass
        `pass_int` to apply that correction.
    """
    est = estimate_first_downs(
        {"rec": rec, "rush_att": rush_att, "rec_yd": rec_yd, "rush_yd": rush_yd},
        position,
        profile=profile,
    )
    fd_points = 0.5 * (est["rec_fd"] + est["rush_fd"])

    int_adj = 0.0
    if pass_int:
        int_adj = (LEAGUE_SCORING["pass_int"] - float(source_int_penalty)) * float(pass_int)

    return {
        "league_points": round(float(half_ppr_pts) + fd_points + int_adj, 2),
        "half_ppr_points": round(float(half_ppr_pts), 2),
        "first_down_points": round(fd_points, 2),
        "interception_adjustment": round(int_adj, 2),
        "estimated_first_downs": est,
    }


def first_down_premium(position, rec_per_game=0.0, rush_att_per_game=0.0, profile=None):
    """Points per game a player gains purely from the first-down rule.

    This is the number to quote when nudging a player up or down relative to
    his half-PPR ADP. A 6-catch possession WR is worth roughly +2 ppg over his
    price; a 3-catch deep threat roughly +0.8.
    """
    est = estimate_first_downs(
        {"rec": rec_per_game, "rush_att": rush_att_per_game}, position, profile=profile
    )
    return round(0.5 * (est["rec_fd"] + est["rush_fd"]), 2)


def rank_projections(players, scoring=None):
    """Re-rank a list of projections into league points and report how far each
    player moved versus his half-PPR ordering. Movers are the actionable output.

    Each player: {"name", "position", "half_ppr_ppg", "rec_pg", "rush_att_pg",
                  "profile"} or {"name", "position", "stats": {...}}
    """
    rows = []
    for p in players or []:
        pos = (p.get("position") or "WR").upper()
        if "stats" in p:
            lg = score_stat_line(p["stats"], scoring=scoring, position=pos)
            hp = half_ppr_points(p["stats"], scoring=scoring)
        else:
            conv = league_points_from_half_ppr(
                p.get("half_ppr_ppg", 0.0),
                pos,
                rec=p.get("rec_pg"),
                rush_att=p.get("rush_att_pg"),
                profile=p.get("profile"),
                pass_int=p.get("pass_int_pg"),
            )
            lg = conv["league_points"]
            hp = conv["half_ppr_points"]
        rows.append(
            {
                "name": p.get("name"),
                "position": pos,
                "league_ppg": round(lg, 2),
                "half_ppr_ppg": round(hp, 2),
                "fd_premium": round(lg - hp, 2),
                "vorp": round(lg - REPLACEMENT_PPG.get(pos, 10.0), 2),
            }
        )

    by_half = sorted(rows, key=lambda r: -r["half_ppr_ppg"])
    half_rank = {id(r): i + 1 for i, r in enumerate(by_half)}
    by_league = sorted(rows, key=lambda r: -r["league_ppg"])
    for i, r in enumerate(by_league):
        r["league_rank"] = i + 1
        r["half_ppr_rank"] = half_rank[id(r)]
        r["rank_delta"] = r["half_ppr_rank"] - r["league_rank"]  # +ve = rises here
    return by_league


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _demo():
    possession = {"rec": 7, "rec_yd": 68, "rec_fd": 5}
    deep = {"rec": 3, "rec_yd": 88, "rec_td": 1, "rec_fd": 2}
    out = {
        "possession_wr": score_breakdown(possession, position="WR"),
        "deep_threat_wr": score_breakdown(deep, position="WR"),
        "premium_6catch_slot": first_down_premium("WR", rec_per_game=6, profile="possession"),
        "premium_3catch_deep": first_down_premium("WR", rec_per_game=3, profile="deep_threat"),
        "premium_workhorse_rb": first_down_premium("RB", rec_per_game=3, rush_att_per_game=17),
        "replacement_ppg": REPLACEMENT_PPG,
    }
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--demo" in argv:
        print(json.dumps(_demo(), indent=2))
        return 0
    if argv and os.path.exists(argv[0]):
        payload = json.load(open(argv[0]))
    else:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    if "players" in payload:
        print(json.dumps(rank_projections(payload["players"]), indent=2))
    else:
        print(
            json.dumps(
                score_breakdown(
                    payload.get("stats", payload), position=payload.get("position")
                ),
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
