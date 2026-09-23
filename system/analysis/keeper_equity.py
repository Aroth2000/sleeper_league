#!/usr/bin/env python3
"""
keeper_equity.py -- Part 5 of the plan. The league's biggest non-obvious edge.

The rule that creates the edge: **a player added off waivers or free agency
costs a 12th-round pick to keep next season.** A drafted player costs the round
he was drafted in. Identical production, wildly different franchise value.

  A breakout rookie RB claimed in Week 7 who finishes as an RB2 is keepable in
  2027 for a TWELFTH. The same RB2 production from a player drafted in round 3
  is keepable only at third-round cost. Nine rounds of surplus, for free, for
  the price of a Tuesday waiver claim.

So every waiver recommendation carries a keeper flag alongside its win-now
value, and once Andrew's playoff fate is settled the objective flips: stash
ascending young players rather than chase marginal veteran upgrades.

Surplus is measured in ROUNDS, not points, because rounds are the currency the
rule is written in:

    surplus_rounds = keeper_cost_round - market_round

where market_round is where that player would actually go in next year's draft.
Positive surplus = you are buying him below market. Bo Nix at a 12th when a
QB of his projection goes in round 5 is +7 rounds of surplus.

Eligibility rules enforced here (all from league_config.keeper_rules):
  * max 3 keepers
  * 1st-round picks are NOT keeper-eligible
  * the round you KEPT him at carries forward as next year's cost
  * no player may be kept more than 3 CONSECUTIVE years

Public API
----------
    market_round(position, projected_ppg=..., tier=...)  -> int
    keeper_cost(player)                                  -> {cost_round, eligible, ...}
    evaluate_keeper(player)                              -> full equity row
    build_keeper_board(players)                          -> sorted rows
    optimal_keeper_slate(players, max_keepers=3)         -> the legal best 3
    waiver_add_equity(player)                            -> equity of a 12th-round add
    forfeited_overall_pick(round, slot)                  -> snake-draft pick number
    keeper_vs_winnow_weight(week, ...)                   -> season-phase tilt

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

try:
    from .scoring import REPLACEMENT_PPG
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scoring import REPLACEMENT_PPG

__all__ = [
    "WAIVER_KEEPER_COST_ROUND",
    "MAX_KEEPERS",
    "MAX_CONSECUTIVE_YEARS",
    "DRAFT_ROUNDS",
    "MARKET_ROUND_BY_PPG",
    "TIER_TO_ROUND",
    "SURPLUS_GRADES",
    "market_round",
    "forfeited_overall_pick",
    "keeper_cost",
    "evaluate_keeper",
    "build_keeper_board",
    "optimal_keeper_slate",
    "waiver_add_equity",
    "andrew_roster_from_config",
    "keeper_vs_winnow_weight",
    "load_rules",
]

WAIVER_KEEPER_COST_ROUND = 12
MAX_KEEPERS = 3
MAX_CONSECUTIVE_YEARS = 3
DRAFT_ROUNDS = 15
NUM_TEAMS = 10
FIRST_ROUND_INELIGIBLE = True

# --------------------------------------------------------------------------
# Market round: where a player of this projection actually goes in a 10-team,
# 16-round SUPERFLEX draft with half-PPR + 0.5/first-down scoring.
#
# SUPERFLEX is why the QB table is so aggressive: with 10 QB slots plus 10
# SUPER_FLEX slots in a 10-team league, ~17 QBs start every week, so a QB who
# would be a round-9 pick in a 1QB league is a round-4 pick here. Any keeper
# maths that uses a generic ADP will systematically undervalue QB keepers, and
# Bo Nix at a 12th is exactly the case that mistake ruins.
#
# ppg here is THIS league's points per game (see scoring.py). Thresholds are
# descending; the first one met wins. Calibration constants -- override via
# league_config or the `market_table` kwarg once real scoring exists.
# --------------------------------------------------------------------------

MARKET_ROUND_BY_PPG = {
    "QB": [(24.0, 1), (22.0, 2), (20.5, 3), (19.0, 4), (18.0, 5), (17.0, 6),
           (16.0, 8), (15.0, 10), (13.5, 12), (0.0, 15)],
    "RB": [(19.0, 1), (17.0, 2), (15.5, 3), (14.0, 4), (13.0, 5), (12.0, 6),
           (11.0, 8), (10.0, 10), (9.0, 12), (0.0, 15)],
    "WR": [(19.0, 1), (17.0, 2), (15.5, 3), (14.0, 4), (13.0, 5), (12.0, 6),
           (11.0, 8), (10.0, 10), (9.0, 12), (0.0, 15)],
    "TE": [(15.0, 1), (13.0, 2), (11.5, 3), (10.5, 4), (9.5, 6), (8.5, 8),
           (7.5, 10), (0.0, 14)],
    "DEF": [(9.0, 13), (7.0, 15), (0.0, 15)],
    "K": [(0.0, 15)],
}

# Analysts speak in tiers far more often than in ppg, so accept both.
TIER_TO_ROUND = {
    "QB1": 2, "QB2": 6, "QB3": 10, "QB4": 14,
    "RB1": 2, "RB2": 5, "RB3": 9, "RB4": 13,
    "WR1": 2, "WR2": 5, "WR3": 9, "WR4": 13,
    "TE1": 3, "TE2": 8, "TE3": 12,
    "DEF1": 13, "DEF2": 15,
}

SURPLUS_GRADES = [(7, "very high"), (4, "high"), (2, "medium"), (0, "low")]


def load_rules(config_path=None):
    """Pull keeper rules from league_config.json when it exists, so a rules
    change is a config edit rather than a code edit."""
    if config_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(here, "..", "league_config.json")
    rules = {
        "max_keepers": MAX_KEEPERS,
        "undrafted_pickup_cost_round": WAIVER_KEEPER_COST_ROUND,
        "max_consecutive_years": MAX_CONSECUTIVE_YEARS,
        "first_round_ineligible": FIRST_ROUND_INELIGIBLE,
        "draft_rounds": DRAFT_ROUNDS,
        "num_teams": NUM_TEAMS,
    }
    try:
        with open(config_path) as fh:
            cfg = json.load(fh)
    except (IOError, OSError, ValueError):
        return rules
    for k, v in (cfg.get("keeper_rules") or {}).items():
        if not k.startswith("_") and v is not None:
            rules[k] = v
    lg = cfg.get("league") or {}
    rules["draft_rounds"] = lg.get("draft_rounds", rules["draft_rounds"])
    rules["num_teams"] = lg.get("num_teams", rules["num_teams"])
    rules["draft_slot"] = lg.get("andrew_draft_slot")
    return rules


# --------------------------------------------------------------------------
# Market value
# --------------------------------------------------------------------------

def market_round(position, projected_ppg=None, tier=None, market_table=None,
                 default_round=None):
    """Where this player would be drafted next year, in rounds.

    Explicit `tier` wins if given ("RB2"), otherwise projected league ppg is
    mapped through the positional table. Returns DRAFT_ROUNDS+1 for a player
    who would not be drafted at all -- which correctly makes any keeper cost
    look like a loss.
    """
    pos = (position or "WR").upper()
    if tier:
        t = str(tier).upper().replace(" ", "")
        if t in TIER_TO_ROUND:
            return TIER_TO_ROUND[t]
    if projected_ppg is None:
        return default_round if default_round is not None else DRAFT_ROUNDS + 1
    table = (market_table or MARKET_ROUND_BY_PPG).get(pos)
    if not table:
        table = MARKET_ROUND_BY_PPG["WR"]
    for threshold, rnd in table:
        if float(projected_ppg) >= threshold:
            return rnd
    return DRAFT_ROUNDS + 1


def forfeited_overall_pick(round_number, slot, num_teams=NUM_TEAMS, snake=True):
    """Which overall pick you actually give up. Snake matters: from slot 8 in a
    10-team league a 4th-round keeper costs pick 33, not pick 38."""
    r = int(round_number)
    s = int(slot)
    if snake and r % 2 == 0:
        s = num_teams - s + 1
    return (r - 1) * num_teams + s


def _grade(surplus):
    for threshold, label in SURPLUS_GRADES:
        if surplus >= threshold:
            return label
    return "none"


# --------------------------------------------------------------------------
# Cost and eligibility
# --------------------------------------------------------------------------

def keeper_cost(player, rules=None):
    """What it costs to keep this player NEXT season, and whether that is legal.

    player keys (all optional except acquisition):
      acquisition: "draft" | "keeper" | "waiver" | "free_agent" | "trade" | "undrafted"
      draft_round / kept_at_round : the round he was drafted or kept at
      consecutive_years_kept      : how many straight years he has been kept SO FAR
    """
    rules = rules or load_rules()
    acq = str(player.get("acquisition") or player.get("acquired") or "").lower()
    waiver_round = int(rules.get("undrafted_pickup_cost_round", WAIVER_KEEPER_COST_ROUND))
    notes = []
    escalated = False  # True when this cost came from N-1 escalation of a prior keep

    kept_at = player.get("kept_at_round")
    drafted = player.get("draft_round")

    if kept_at is not None:
        # He was KEPT last year at round `kept_at`. Under this league's N-1 rule the
        # cost to keep him AGAIN is one round cheaper in NUMBER (floored at R1).
        prev = int(kept_at)
        cost = max(1, prev - 1)
        escalated = True
        if cost < prev:
            notes.append("kept at round %d last year; N-1 escalation -> this year costs round %d" % (prev, cost))
        else:
            notes.append("kept at round %d last year; already at the R1 floor -> stays round %d" % (prev, cost))
    elif acq.startswith("waiver") or acq in ("free_agent", "fa", "undrafted", "add"):
        cost = waiver_round
        notes.append("added off waivers/FA, never drafted -> costs a %dth" % waiver_round)
    elif drafted is not None:
        # First-time keep: costs the round he was drafted, with no N-1 discount yet.
        cost = int(drafted)
        notes.append("first-time keep; drafted in round %d" % cost)
    elif acq == "trade":
        cost = int(player.get("original_draft_round") or waiver_round)
        notes.append("acquired by trade; cost follows his original draft round "
                     "(assumed %d if undrafted)" % waiver_round)
    else:
        cost = waiver_round
        notes.append("acquisition unknown -- assumed a waiver add at a %dth. VERIFY."
                     % waiver_round)

    years = int(player.get("consecutive_years_kept") or 0)
    eligible = True
    reason = None
    # The R1 restriction applies to a player's ORIGINAL draft round, not to a cost
    # that has escalated into R1 via N-1. An escalated R1 cost is valid (but final).
    if rules.get("first_round_ineligible", True) and cost <= 1 and not escalated:
        eligible = False
        reason = "1st-round pick -- not keeper-eligible (original draft round)"
    max_years = int(rules.get("max_consecutive_years", MAX_CONSECUTIVE_YEARS))
    if years >= max_years:
        eligible = False
        reason = ("already kept %d consecutive years; the %d-year cap is reached"
                  % (years, max_years))

    years_after = years + 1
    cost_floor_reached = escalated and cost <= 1
    final_year = eligible and (years_after >= max_years or cost_floor_reached)
    if eligible and cost_floor_reached:
        notes.append("cost has escalated to the R1 floor -- valid this year but NOT "
                     "keepable again (no R0 to escalate to); final eligible year")
    elif final_year:
        notes.append("FINAL eligible year -- keeping him uses up the %d-year cap"
                     % max_years)

    return {
        "cost_round": cost,
        "eligible": eligible,
        "ineligible_reason": reason,
        "consecutive_years_kept": years,
        "consecutive_years_if_kept": years_after,
        "is_final_eligible_year": final_year,
        "years_of_control_remaining": max(0, max_years - years) if eligible else 0,
        "notes": notes,
    }


def evaluate_keeper(player, rules=None, draft_slot=None, market_table=None,
                    season=2027):
    """Full 2027 keeper-equity row for one player."""
    rules = rules or load_rules()
    slot = draft_slot if draft_slot is not None else rules.get("draft_slot") or 8
    pos = (player.get("position") or player.get("pos") or "WR").upper()

    cost = keeper_cost(player, rules=rules)
    tier = player.get("tier") or player.get("ros_tier")
    valued = (player.get("market_round") is not None
              or player.get("projected_ppg") is not None
              or bool(tier))

    mkt = player.get("market_round")
    if mkt is None and valued:
        mkt = market_round(pos, projected_ppg=player.get("projected_ppg"),
                           tier=tier, market_table=market_table)
    mkt = int(mkt) if mkt is not None else None

    # An unprojected player must NOT report a fake negative surplus. Treating
    # "we have no projection" as "he is worthless" would tell the synthesis
    # agent to drop Travis Kelce, which is exactly the kind of confident,
    # authoritative-looking error this layer exists to prevent.
    if not cost["eligible"]:
        surplus, grade = 0, "none"
    elif not valued:
        surplus, grade = None, "unknown"
    else:
        surplus = cost["cost_round"] - mkt
        grade = _grade(surplus)

    row = {
        "player": player.get("player") or player.get("name"),
        "player_id": player.get("player_id"),
        "position": pos,
        "acquired": player.get("acquisition") or player.get("acquired"),
        "keeper_cost_%d" % season: "R%d" % cost["cost_round"],
        "keeper_cost_round": cost["cost_round"],
        "market_round": mkt,
        "projected_ppg": player.get("projected_ppg"),
        "projected_value": tier or (
            "%.1f ppg" % player["projected_ppg"] if player.get("projected_ppg") else "unknown"),
        "surplus_rounds": surplus,
        "surplus": grade,
        "valued": valued,
        "eligible": cost["eligible"],
        "ineligible_reason": cost["ineligible_reason"],
        "consecutive_years_if_kept": cost["consecutive_years_if_kept"],
        "is_final_eligible_year": cost["is_final_eligible_year"],
        "forfeits_overall_pick": forfeited_overall_pick(
            cost["cost_round"], slot, num_teams=rules.get("num_teams", NUM_TEAMS)),
        "notes": list(cost["notes"]),
    }
    if not valued:
        row["notes"].append("NO PROJECTION SUPPLIED -- surplus is unknown, not zero and "
                            "not negative. Do not rank or drop on this row.")
    if cost["eligible"] and surplus is not None and surplus >= 7:
        row["notes"].append("elite surplus: this is the kind of asset the 12th-round "
                            "waiver rule exists to create")
    return row


def build_keeper_board(players, rules=None, draft_slot=None, market_table=None,
                       season=2027, include_ineligible=True):
    """Rank a roster (or the waiver pool) by 2027 keeper surplus."""
    rules = rules or load_rules()
    rows = [evaluate_keeper(p, rules=rules, draft_slot=draft_slot,
                            market_table=market_table, season=season)
            for p in players or []]
    if not include_ineligible:
        rows = [r for r in rows if r["eligible"]]

    def sort_key(r):
        eligible = 0 if r["eligible"] else 1
        unvalued = 0 if r["surplus_rounds"] is not None else 1
        surplus = -(r["surplus_rounds"] or 0)
        # Among unprojected players the cheapest keeper cost is the most likely
        # bargain, so those sort by cost round DESCENDING (R14 before R2).
        tiebreak = r["market_round"] if r["market_round"] is not None else -r["keeper_cost_round"]
        return (eligible, unvalued, surplus, tiebreak)

    rows.sort(key=sort_key)
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def optimal_keeper_slate(players, max_keepers=None, rules=None, draft_slot=None,
                         market_table=None, season=2027):
    """The legal best set of keepers, plus the ones just missing the cut.

    Greedy is optimal here: keeper slots are interchangeable and each player's
    surplus is independent of the others, so taking the top-N by surplus IS the
    maximum. The only structure to respect is eligibility.
    """
    rules = rules or load_rules()
    n = int(max_keepers if max_keepers is not None else rules.get("max_keepers", MAX_KEEPERS))
    board = build_keeper_board(players, rules=rules, draft_slot=draft_slot,
                               market_table=market_table, season=season)
    eligible = [r for r in board if r["eligible"]]
    # Only players with a real valuation can be ranked. Unprojected players are
    # held back rather than silently sorted to the bottom, because "we did not
    # project him" and "he is not worth keeping" are completely different facts.
    valued = [r for r in eligible if r["surplus_rounds"] is not None]
    unvalued = [r for r in eligible if r["surplus_rounds"] is None]
    keep = valued[:n]
    return {
        "keep": keep,
        "next_in_line": valued[n:n + 3],
        "needs_projection": unvalued,
        "provisional": bool(unvalued),
        "ineligible": [r for r in board if not r["eligible"]],
        "total_surplus_rounds": sum(r["surplus_rounds"] for r in keep),
        "picks_forfeited": sorted(r["forfeits_overall_pick"] for r in keep),
        "aging_out": [r["player"] for r in keep if r["is_final_eligible_year"]],
        "slots_used": len(keep),
        "slots_available": n,
    }


def waiver_add_equity(player, rules=None, draft_slot=None, market_table=None,
                      season=2027):
    """Equity of a player Andrew could add off waivers THIS week.

    Any such add is keepable at a 12th regardless of what he does, which is why
    a mid-season breakout is worth more than the same production from a drafted
    player. This is the number that belongs on every waiver recommendation.
    """
    p = dict(player)
    p.setdefault("acquisition", "waiver")
    p.pop("draft_round", None)
    p.pop("kept_at_round", None)
    p["consecutive_years_kept"] = 0
    row = evaluate_keeper(p, rules=rules, draft_slot=draft_slot,
                          market_table=market_table, season=season)
    row["keeper_equity_%d" % season] = row["surplus"]
    return row


def andrew_roster_from_config(config_path=None, projections=None, season=2026):
    """Andrew's roster as keeper-equity input, straight from league_config's
    2026 keeper-cost board (computed from the real 2025 draft).

    YEAR FRAME MATTERS, and getting it wrong silently corrupts the 3-year cap:

      season=2026 (default) -- the decision on the table right now. cost_round
        from the board is what it costs to keep him this August, and
        kept_in_2025 means he already has one year on the consecutive clock.

      season=2027 -- next year's board. This only means anything for the players
        Andrew actually keeps in 2026: their cost carries forward unchanged and
        their clock advances by one. Everyone else re-enters the draft pool, so
        their 2027 cost depends on where they are drafted and cannot be known
        yet; they are returned with `cost_basis_unknown` set so a caller never
        quotes a number that does not exist.

    projections: optional {player_id or name: projected league ppg}.
    """
    if config_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(here, "..", "league_config.json")
    try:
        with open(config_path) as fh:
            cfg = json.load(fh)
    except (IOError, OSError, ValueError):
        return []
    projections = projections or {}
    andrew = cfg.get("andrew") or {}
    planned = {k.get("player_id") for k in
               ((andrew.get("keeper_plan") or {}).get("keeping") or [])}

    out = []
    for row in andrew.get("keeper_cost_board_2026") or []:
        pid = row.get("player_id")
        name = row.get("name")
        years = 1 if row.get("kept_in_2025") else 0
        kept_last_year = bool(row.get("kept_in_2025"))
        entry = {
            "player": name,
            "player_id": pid,
            "position": row.get("pos"),
            "acquisition": "keeper" if kept_last_year else "draft",
            "consecutive_years_kept": years,
            "projected_ppg": projections.get(pid, projections.get(name)),
            "flag": row.get("flag"),
        }
        # A repeat keep (kept in 2025) escalates via N-1 off last year's keep round;
        # a first-time keep just costs his 2025 draft round. Feed keeper_cost() the
        # field it interprets correctly for each case (kept_at_round => N-1 applies).
        if kept_last_year:
            entry["kept_at_round"] = row.get("cost_round")
        else:
            entry["draft_round"] = row.get("cost_round")
        if season >= 2027:
            if pid in planned:
                # Base 2026 cost, then one more N-1 step per season past 2026.
                base_2026 = (int(row.get("cost_round")) - 1) if kept_last_year else int(row.get("cost_round"))
                prior_year_cost = max(1, base_2026 - (season - 2026 - 1))
                entry.pop("draft_round", None)
                entry["kept_at_round"] = prior_year_cost
                entry["acquisition"] = "keeper"
                entry["consecutive_years_kept"] = years + (season - 2026)
                entry["cost_basis"] = "N-1 escalation from the planned 2026 keep"
            else:
                entry["cost_basis_unknown"] = (
                    "not in the 2026 keeper plan -- he re-enters the draft, so his "
                    "%d cost depends on where he is drafted" % season)
        out.append(entry)
    return out


def keeper_vs_winnow_weight(week, elimination_likely=False, playoff_locked=False,
                            trade_deadline_week=13, playoff_week_start=15):
    """How hard to tilt toward 2027 keeper value instead of this week's points.

    Returns a 0..1 weight on keeper equity (1.0 = ignore win-now entirely) plus
    the posture text. Straight out of Part 5's season-phase rules: in weeks 1-3
    win-now dominates; once elimination is likely the objective flips entirely.
    """
    w = int(week or 0)
    if elimination_likely:
        return {"keeper_weight": 0.9, "posture": "eliminated or nearly so -- flip the "
                "objective to 2027 keeper accumulation; stash ascending young players "
                "over marginal veteran upgrades", "phase": "salvage"}
    if w >= playoff_week_start:
        return {"keeper_weight": 0.25 if not playoff_locked else 0.45,
                "posture": "playoffs -- win now, but a free roster spot goes to a stash",
                "phase": "playoffs"}
    if playoff_locked and w >= 12:
        return {"keeper_weight": 0.6, "posture": "seed is secure -- start banking "
                "12th-round keeper equity with spare roster spots", "phase": "coasting"}
    if w >= trade_deadline_week:
        return {"keeper_weight": 0.4, "posture": "post-deadline -- roster is what it is; "
                "spare spots should hold 2027 assets", "phase": "post_deadline"}
    if w <= 3:
        return {"keeper_weight": 0.2, "posture": "small-sample weeks -- win now, and do "
                "not cut a good player for a one-week wonder", "phase": "small_sample"}
    return {"keeper_weight": 0.3, "posture": "core season -- keeper equity is a "
            "tiebreaker between similar win-now options", "phase": "core"}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _demo():
    andrews = [
        {"player": "Kenneth Walker", "position": "RB", "draft_round": 4,
         "acquisition": "draft", "consecutive_years_kept": 0, "projected_ppg": 14.2},
        {"player": "Bo Nix", "position": "QB", "kept_at_round": 12,
         "acquisition": "keeper", "consecutive_years_kept": 1, "projected_ppg": 18.4},
        {"player": "Jameson Williams", "position": "WR", "kept_at_round": 14,
         "acquisition": "keeper", "consecutive_years_kept": 1, "projected_ppg": 12.6},
        {"player": "Puka Nacua", "position": "WR", "kept_at_round": 2,
         "acquisition": "keeper", "consecutive_years_kept": 1, "projected_ppg": 17.5},
        {"player": "Ashton Jeanty", "position": "RB", "draft_round": 1,
         "acquisition": "draft", "projected_ppg": 18.0},
        {"player": "Travis Kelce", "position": "TE", "draft_round": 7,
         "acquisition": "draft", "projected_ppg": 10.8},
    ]
    waiver = {"player": "Dylan Sampson", "position": "RB", "projected_ppg": 13.1}
    return {
        "slate": optimal_keeper_slate(andrews),
        "waiver_add": waiver_add_equity(waiver),
        "phase_week_16_eliminated": keeper_vs_winnow_weight(16, elimination_likely=True),
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--andrew" in argv:
        print(json.dumps(build_keeper_board(andrew_roster_from_config()), indent=2))
        return 0
    if not argv or "--demo" in argv:
        print(json.dumps(_demo(), indent=2))
        return 0
    with open(argv[0]) as fh:
        payload = json.load(fh)
    players = payload if isinstance(payload, list) else payload.get("players", [])
    print(json.dumps(build_keeper_board(players), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
