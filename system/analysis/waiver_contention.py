#!/usr/bin/env python3
"""
waiver_contention.py -- turn a flat wishlist into an ORDERED claim sheet.

The problem this solves: a ranked free-agent board tells you who is good. It
does not tell you who you can actually get. Four teams pick ahead of Andrew in
the reverse-standings order, and if three of them just lost a running back, the
best RB on the board is not a claim -- he is a fantasy. Meanwhile the WR nobody
else has a hole at is a near-certain add. Ordering claims by value alone burns
priority on players who were never going to reach you.

Waiver mode
-----------
league_config.json resolves this as `reverse_standings_rolling_priority`
(waiver_type == 1, and 2025 transactions carry settings.priority with an empty
waiver_budget). The 100-unit budget field is Sleeper boilerplate. BUT the plan
lists this as an open question, so this module supports:

    mode="rolling_priority"  (default, matches the resolved config)
    mode="faab"
    mode="both"              runs both and flags the ambiguity loudly

Rolling-priority model
----------------------
A closed-form product of independent claims is wrong here, because priority is
consumed: a team that wins its first claim drops to the BACK of the order and
stops threatening everything else in the same run. That coupling is the whole
mechanic, so this module runs a seeded Monte Carlo of the actual processing
order rather than multiplying probabilities.

Each trial:
  1. Sample which rivals genuinely submit for which players (Bernoulli on the
     likelihoods produced by opponent_pressure).
  2. Process the run: the highest-priority team with a pending, still-available
     claim takes its top choice, then moves to the back of the order.
  3. Stop when Andrew becomes the highest-priority team with a pending claim --
     that is his turn. Snapshot who is still on the board.

P(reaches Andrew) is the fraction of trials in which the player survived to that
snapshot. Seeded, so the same inputs always give the same sheet.

Claim ORDERING is a separate question from probability. In a rolling-priority
league a failed claim costs nothing -- Sleeper simply moves to your next claim
in the list -- so a long shot placed first is free. Only a *successful* claim
consumes priority. Ordering is therefore value-dominant with a square-root
probability discount (ALPHA_ROLLING = 0.5). Under FAAB a losing bid also costs
nothing, but the winning bid costs real budget, so probability weighs full
(ALPHA_FAAB = 1.0) and the bid recommendation carries the tradeoff.

Public API
----------
    contention_report(...)          -> CONTENTION_SCHEMA-shaped dict (main entry)
    simulate_rolling_priority(...)  -> {player: P(reaches Andrew)}
    survival_closed_form(...)       -> fast analytic approximation, for sanity checks
    faab_recommendations(...)       -> {player: {bid_pct, win_probability, ...}}

Pure stdlib (random with an explicit seed).
"""

from __future__ import annotations

import bisect
import json
import os
import random
import sys

__all__ = [
    "ALPHA_ROLLING",
    "ALPHA_FAAB",
    "DEFAULT_TRIALS",
    "DEFAULT_SEED",
    "normalise_rival_claims",
    "teams_ahead",
    "simulate_rolling_priority",
    "survival_closed_form",
    "faab_recommendations",
    "build_claim_sheet",
    "contention_report",
]

DEFAULT_TRIALS = 4000
DEFAULT_SEED = 20260807
ALPHA_ROLLING = 0.5   # failed claims are free -> discount probability gently
ALPHA_FAAB = 1.0      # a won bid costs budget -> price probability fully

QUIET_WIN_P = 0.85
DO_NOT_BOTHER_P = 0.12


# --------------------------------------------------------------------------
# Input normalisation
# --------------------------------------------------------------------------

def _pname(x):
    if isinstance(x, dict):
        return x.get("player") or x.get("name") or x.get("player_id")
    return x


def normalise_rival_claims(rival_claims):
    """Accept any of the shapes the upstream agents actually emit and return
    {team: [(player, likelihood), ...]} in each team's own preference order.

    Shapes handled:
      {"DannyBC1": ["Player A", "Player B"]}
      {"DannyBC1": [{"player": "A", "likelihood": 0.8}, ...]}
      [{"team": "DannyBC1", "predicted_claims": [...]}, ...]   (OPPONENT_SCHEMA)
    """
    out = {}
    if rival_claims is None:
        return out
    if isinstance(rival_claims, list):
        table = {}
        for block in rival_claims:
            if not isinstance(block, dict):
                continue
            key = (block.get("team") or block.get("owner")
                   or block.get("roster_id"))
            if key is None:
                continue
            table[str(key)] = block.get("predicted_claims") or block.get("claims") or []
        rival_claims = table

    for team, claims in rival_claims.items():
        rows = []
        for c in claims or []:
            if isinstance(c, dict):
                lk = c.get("likelihood", c.get("probability", 0.6))
                rows.append((_pname(c), max(0.0, min(1.0, float(lk)))))
            elif isinstance(c, (tuple, list)) and len(c) == 2:
                # already normalised -- this function must be idempotent, because
                # callers legitimately normalise once and pass the result on
                rows.append((_pname(c[0]), max(0.0, min(1.0, float(c[1])))))
            else:
                rows.append((_pname(c), 0.6))
        # Preference order = the order given, but a sharply higher likelihood
        # further down the list means that IS their preference. Stable sort by
        # likelihood keeps the supplied order among equals.
        rows = [r for r in rows if r[0]]
        rows.sort(key=lambda r: -r[1])
        out[str(team)] = rows
    return out


def teams_ahead(priority_order, andrew, andrew_priority=None):
    """Everyone who gets to act before Andrew. Accepts either an explicit
    identifier for Andrew inside priority_order, or a 1-based priority."""
    order = [str(t) for t in (priority_order or [])]
    idx = None
    if andrew is not None and str(andrew) in order:
        idx = order.index(str(andrew))
    elif andrew_priority is not None:
        idx = int(andrew_priority) - 1
    if idx is None or idx < 0:
        return order, None
    return order[:idx], idx


# --------------------------------------------------------------------------
# Rolling priority: seeded simulation of the actual processing run
# --------------------------------------------------------------------------

def simulate_rolling_priority(targets, priority_order, rival_claims, andrew=None,
                              andrew_priority=None, trials=DEFAULT_TRIALS,
                              seed=DEFAULT_SEED, allow_multiple_wins=True):
    """P(each target is still unclaimed when Andrew's turn arrives).

    targets: [{"player", ...}] -- the players Andrew wants.
    rival_claims may include players Andrew is NOT targeting; those still matter,
    because a rival spending priority on someone else is a rival who is no
    longer a threat to Andrew's board. That interaction is exactly what the
    simulation is for.

    allow_multiple_wins mirrors Sleeper: a team that wins a claim drops to the
    back of the order but its remaining claims stay live for the same run.
    """
    rng = random.Random(seed)
    names = [_pname(t) for t in targets]
    claims = normalise_rival_claims(rival_claims)
    order, andrew_idx = teams_ahead(priority_order, andrew, andrew_priority)
    full_order = [str(t) for t in (priority_order or [])]
    if andrew is not None and str(andrew) in full_order:
        andrew_key = str(andrew)
    else:
        andrew_key = "__ANDREW__"
        if andrew_idx is None:
            andrew_idx = len(full_order)
        full_order = full_order[:andrew_idx] + [andrew_key] + full_order[andrew_idx:]

    survived = {n: 0 for n in names}
    if not names:
        return {}

    for _ in range(trials):
        wants = {}
        for team, rows in claims.items():
            if team == andrew_key:
                continue
            picked = [p for p, lk in rows if rng.random() < lk]
            if picked:
                wants[team] = picked
        available = set(names) | {p for lst in wants.values() for p in lst}
        queue = list(full_order)
        for team in wants:
            if team not in queue:
                # A rival absent from the priority order is placed behind Andrew,
                # which is the optimistic read. contention_report flags this case
                # rather than letting it pass silently.
                queue.append(team)

        guard = 0
        while guard < 200:
            guard += 1
            actor = None
            for team in queue:
                if team == andrew_key:
                    if any(n in available for n in names):
                        actor = andrew_key
                    break  # Andrew's slot reached: nobody behind him acts first
                pending = [p for p in wants.get(team, []) if p in available]
                if pending:
                    actor = team
                    break
            if actor is None or actor == andrew_key:
                break
            take = next(p for p in wants[actor] if p in available)
            available.discard(take)
            wants[actor] = [p for p in wants[actor] if p != take]
            if not allow_multiple_wins:
                wants[actor] = []
            queue.remove(actor)
            queue.append(actor)

        for n in names:
            if n in available:
                survived[n] += 1

    return {n: round(survived[n] / float(trials), 3) for n in names}


def survival_closed_form(targets, priority_order, rival_claims, andrew=None,
                         andrew_priority=None):
    """Analytic approximation: P = prod over teams ahead of (1 - p_take).

    p_take is discounted by where the player sits in that team's own preference
    list, because a team that lands its first choice has already dropped to the
    back of the queue. Cheaper and explainable, but it ignores cross-target
    coupling, so the simulation is authoritative. Kept for sanity-checking and
    for the case where a caller wants a number with no RNG involved at all.
    """
    claims = normalise_rival_claims(rival_claims)
    ahead, _ = teams_ahead(priority_order, andrew, andrew_priority)
    ahead = set(ahead)
    out = {}
    for t in targets:
        name = _pname(t)
        p_survive = 1.0
        for team in ahead:
            rows = claims.get(team, [])
            for rank, (player, lk) in enumerate(rows):
                if player != name:
                    continue
                # each earlier preference they might land first blunts this one
                blunt = 1.0
                for prev_player, prev_lk in rows[:rank]:
                    blunt *= (1.0 - prev_lk * 0.8)
                p_survive *= (1.0 - lk * blunt)
                break
        out[name] = round(p_survive, 3)
    return out


# --------------------------------------------------------------------------
# FAAB mode
# --------------------------------------------------------------------------

# Rivals do not bid their true valuation. This is the spread of multipliers
# applied to a rival's "fair" bid, with weights -- a coarse but honest model of
# a 10-team room where two people always overpay and two always lowball.
BID_MULTIPLIERS = [(0.35, 0.18), (0.6, 0.22), (0.9, 0.25), (1.25, 0.2), (1.8, 0.15)]


def _fair_bid_pct(value_norm, aggression=1.0):
    """A rival's 'fair' bid as a percent of a 100-unit budget. A league-winning
    add goes for ~40%; a streamer goes for low single digits."""
    return max(1.0, 45.0 * (value_norm ** 1.6) * aggression)


def faab_recommendations(targets, rival_claims, priority_order=None, andrew=None,
                         budgets=None, andrew_budget=100.0, target_win_prob=0.65,
                         trials=DEFAULT_TRIALS, seed=DEFAULT_SEED,
                         max_share_of_budget=0.5, value_key="value"):
    """Recommended bid per target, and the win probability it buys.

    budgets: {team: remaining budget pct}. A rival with 6% left is not a threat
    on anything, which is the single most useful fact in a FAAB league.
    """
    rng = random.Random(seed + 1)
    claims = normalise_rival_claims(rival_claims)
    budgets = {str(k): float(v) for k, v in (budgets or {}).items()}
    andrew_key = str(andrew) if andrew is not None else "__ANDREW__"

    vals = [float(t.get(value_key, 0.0) or 0.0) for t in targets] or [1.0]
    top = max(vals) or 1.0

    out = {}
    for t in targets:
        name = _pname(t)
        vnorm = (float(t.get(value_key, 0.0) or 0.0) / top) if top else 0.0
        interested = []
        for team, rows in claims.items():
            if team == andrew_key:
                continue
            for player, lk in rows:
                if player == name:
                    interested.append((team, lk, budgets.get(team, 100.0)))
                    break

        # Distribution of the highest rival bid, sampled.
        max_bids = []
        for _ in range(trials):
            best = 0.0
            for team, lk, bud in interested:
                if rng.random() >= lk:
                    continue
                mult = _weighted_choice(rng, BID_MULTIPLIERS)
                bid = min(bud, _fair_bid_pct(vnorm) * mult)
                best = max(best, bid)
            max_bids.append(best)
        max_bids.sort()

        # Smallest whole-percent bid that wins at least target_win_prob of the time.
        cap = min(andrew_budget, andrew_budget * max_share_of_budget + 1e-9)
        # max_bids is sorted, so bisect_left(bid) is exactly the count of rival
        # outcomes strictly below `bid` -- i.e. the number of trials this bid wins.
        rec = 0
        for bid in range(0, int(andrew_budget) + 1):
            if bisect.bisect_left(max_bids, bid) / float(trials) >= target_win_prob:
                rec = bid
                break
        else:
            rec = int(andrew_budget)
        capped = rec > cap
        rec_final = int(min(rec, cap)) if cap >= 1 else rec
        wins_at_rec = bisect.bisect_left(max_bids, rec_final) / float(trials)

        out[name] = {
            "bid_pct": max(1, rec_final) if interested or vnorm > 0 else 1,
            "win_probability": round(wins_at_rec, 3),
            "interested_teams": [team for team, _, _ in interested],
            "expected_top_rival_bid": round(sum(max_bids) / float(trials), 1),
            "capped_by_budget_policy": capped,
            "notes": ("no rival appears interested - a minimum bid should land him"
                      if not interested else
                      "%d rivals bidding; top rival bid averages %.0f%%"
                      % (len(interested), sum(max_bids) / float(trials))),
        }
    return out


def _weighted_choice(rng, pairs):
    r = rng.random()
    acc = 0.0
    for val, w in pairs:
        acc += w
        if r <= acc:
            return val
    return pairs[-1][0]


# --------------------------------------------------------------------------
# Claim sheet assembly
# --------------------------------------------------------------------------

def build_claim_sheet(targets, probabilities, mode="rolling_priority",
                      faab=None, alpha=None, keeper_bonus_per_round=0.6,
                      value_key="value", roster_spots_open=0):
    """Order the claims. Highest priority_score first.

    priority_score = adjusted_value * P(reaches Andrew) ** alpha

    adjusted_value folds in 2027 keeper surplus (a 12th-round keeper is a real
    asset in this league, see keeper_equity.py) and blocking value.
    """
    if alpha is None:
        alpha = ALPHA_FAAB if mode == "faab" else ALPHA_ROLLING
    rows = []
    for t in targets:
        name = _pname(t)
        p = float(probabilities.get(name, 0.0))
        value = float(t.get(value_key, 0.0) or 0.0)
        keeper_surplus = float(t.get("keeper_surplus_rounds", 0.0) or 0.0)
        adj = value + keeper_bonus_per_round * max(0.0, keeper_surplus)
        if t.get("blocking_value"):
            adj += float(t.get("blocking_value_points", 1.0) or 0.0)
        score = adj * (p ** alpha if p > 0 else 0.0)
        rows.append({
            "player": name,
            "position": (t.get("position") or t.get("pos") or "").upper(),
            "availability_verified": bool(t.get("availability_verified",
                                                t.get("available", False))),
            "contenders_ahead": list(t.get("contenders_ahead") or []),
            "probability_reaches_andrew": round(p, 3),
            "faab_bid_pct": (faab or {}).get(name, {}).get("bid_pct"),
            "drop_to_make_room": t.get("drop_to_make_room") or (
                "none needed - open roster spot" if roster_spots_open > 0 else None),
            "win_now_value": t.get("win_now_value"),
            "keeper_equity_2027": t.get("keeper_equity_2027"),
            "blocking_value": t.get("blocking_value"),
            "value_score": round(value, 2),
            "adjusted_value": round(adj, 2),
            "priority_score": round(score, 3),
            "rationale": t.get("rationale") or _auto_rationale(name, p, value, keeper_surplus, mode),
        })
    rows.sort(key=lambda r: (-r["priority_score"], -r["adjusted_value"]))
    for i, r in enumerate(rows):
        r["order"] = i + 1
    return rows


def _auto_rationale(name, p, value, keeper_surplus, mode):
    if p >= QUIET_WIN_P:
        head = "nobody ahead of Andrew is tracking him - near-certain add"
    elif p <= DO_NOT_BOTHER_P:
        head = "heavily contested, unlikely to reach Andrew"
    else:
        head = "contested, roughly a %d%% chance he survives to Andrew" % round(p * 100)
    tail = ""
    if keeper_surplus >= 4:
        tail = "; carries real 2027 keeper equity at a 12th-round price"
    if mode == "rolling_priority":
        tail += "; a failed claim costs nothing, so listing him high is free"
    return "%s (value %.1f)%s" % (head, value, tail)


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def contention_report(targets, priority_order=None, rival_claims=None, andrew=None,
                      andrew_priority=None, mode="rolling_priority", budgets=None,
                      andrew_budget=100.0, trials=DEFAULT_TRIALS, seed=DEFAULT_SEED,
                      roster_spots_open=0, target_win_prob=0.65,
                      require_availability=True, value_key="value"):
    """The whole thing: probabilities, ordered claim sheet, contention map.

    Shaped to satisfy weekly.js's CONTENTION_SCHEMA.

    require_availability enforces the plan's hard gate (Part 7): a player who
    has not been verified as a free agent IN THIS LEAGUE never reaches the
    claim sheet. He is reported in `rejected` instead. This check lives here,
    in code, precisely so no prompt can talk its way past it.
    """
    mode = (mode or "rolling_priority").lower()
    if mode in ("both_ambiguous", "ambiguous", "unknown"):
        mode = "both"

    flags = []
    assumptions = []
    rejected = []

    usable = []
    for t in targets or []:
        verified = bool(t.get("availability_verified", t.get("available", False)))
        if require_availability and not verified:
            rejected.append({
                "player": _pname(t),
                "reason": "availability not verified against this league's rosters",
            })
            continue
        usable.append(t)
    if rejected:
        flags.append("%d target(s) dropped: availability not verified in this league. "
                     "Hard gate, see plan Part 7." % len(rejected))

    order = [str(t) for t in (priority_order or [])]
    ahead, andrew_idx = teams_ahead(order, andrew, andrew_priority)
    if andrew_idx is None:
        flags.append("Andrew's slot in the priority order could not be located; "
                     "assuming he picks last, which is the pessimistic read.")
    if andrew_priority is not None and andrew is not None and str(andrew) in order:
        if order.index(str(andrew)) + 1 != int(andrew_priority):
            flags.append("andrew_priority=%s disagrees with priority_order position %d. "
                         "Using priority_order." % (andrew_priority, order.index(str(andrew)) + 1))

    claims = normalise_rival_claims(rival_claims)

    unplaced = [t for t in claims if t not in order and t != str(andrew)]
    if unplaced and order:
        flags.append(
            "Rival(s) %s submit claims but do not appear in the priority order, so "
            "they were modelled as picking BEHIND Andrew. That is the optimistic "
            "read -- if any of them actually picks ahead of him, the probabilities "
            "for their targets are too high." % ", ".join(sorted(unplaced)))

    result = {
        "waiver_mode_used": {"rolling_priority": "rolling_priority",
                             "faab": "faab", "both": "both_ambiguous"}[mode],
        "andrew_priority": (andrew_idx + 1) if andrew_idx is not None else (andrew_priority or -1),
        "priority_order": order,
        "teams_ahead_of_andrew": ahead,
        "rejected_unverified": rejected,
    }

    probs = {}
    faab = None

    if mode in ("rolling_priority", "both"):
        probs = simulate_rolling_priority(
            usable, order, claims, andrew=andrew, andrew_priority=andrew_priority,
            trials=trials, seed=seed)
        result["closed_form_check"] = survival_closed_form(
            usable, order, claims, andrew=andrew, andrew_priority=andrew_priority)
        assumptions.append(
            "Rolling priority simulated over %d trials (seed %d): a team that wins a "
            "claim drops to the back of the order, so its remaining threats fade."
            % (trials, seed))
        assumptions.append(
            "A failed claim costs nothing in a priority league, so claims are ordered "
            "value-first with a sqrt(probability) discount rather than by probability.")

    if mode in ("faab", "both"):
        faab = faab_recommendations(
            usable, claims, priority_order=order, andrew=andrew, budgets=budgets,
            andrew_budget=andrew_budget, target_win_prob=target_win_prob,
            trials=trials, seed=seed, value_key=value_key)
        assumptions.append(
            "FAAB bids target a %d%% win rate against a modelled rival bid spread "
            "(0.35x-1.8x of fair value)." % round(target_win_prob * 100))
        if mode == "faab":
            probs = {p: v["win_probability"] for p, v in faab.items()}

    if mode == "both":
        flags.append(
            "WAIVER MODE AMBIGUOUS: league_config resolves waiver_type=1 "
            "(reverse-standings rolling priority) and 2025 transactions show "
            "settings.priority with empty waiver_budget, but the 100-unit budget "
            "field exists in Sleeper. Both models were run; the priority sheet is "
            "authoritative and the FAAB bids are the fallback.")
        result["faab_fallback"] = faab

    sheet = build_claim_sheet(usable, probs, mode=("faab" if mode == "faab" else "rolling_priority"),
                              faab=faab, roster_spots_open=roster_spots_open,
                              value_key=value_key)

    # contention map: who else wants each player, and who is likeliest to win
    cmap = []
    for t in usable:
        name = _pname(t)
        interested = []
        for team, rows in claims.items():
            for player, lk in rows:
                if player == name:
                    interested.append((team, lk))
                    break
        interested.sort(key=lambda x: (order.index(x[0]) if x[0] in order else 99))
        expected = None
        for team, lk in interested:
            if lk >= 0.5:
                expected = team
                break
        if expected is None and probs.get(name, 0) >= 0.5:
            expected = "andrewroth32"
        cmap.append({
            "player": name,
            "interested_teams": [t2 for t2, _ in interested],
            "expected_winner": expected or "unclaimed",
            "probability_reaches_andrew": probs.get(name, 0.0),
        })

    result.update({
        "claim_sheet": sheet,
        "contention_map": cmap,
        "do_not_bother": [r["player"] for r in sheet
                          if r["probability_reaches_andrew"] <= DO_NOT_BOTHER_P],
        "quiet_wins": [r["player"] for r in sheet
                       if r["probability_reaches_andrew"] >= QUIET_WIN_P],
        "assumptions": assumptions,
        "flags": flags,
    })
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _demo():
    targets = [
        {"player": "Dylan Sampson", "position": "RB", "value": 13.5, "available": True,
         "keeper_surplus_rounds": 7},
        {"player": "Keon Coleman", "position": "WR", "value": 11.8, "available": True,
         "keeper_surplus_rounds": 4},
        {"player": "Michael Penix", "position": "QB", "value": 17.2, "available": True},
        {"player": "Jack Bech", "position": "WR", "value": 8.4, "available": True},
    ]
    order = ["DannyBC1", "jpalmeri1616", "LoochCarluccio", "andrewroth32",
             "PeterCrisileo", "havicht", "pdustin", "jomud", "Edeecher", "tlekes"]
    rivals = {
        "DannyBC1": [{"player": "Dylan Sampson", "likelihood": 0.85},
                     {"player": "Keon Coleman", "likelihood": 0.3}],
        "jpalmeri1616": [{"player": "Dylan Sampson", "likelihood": 0.6},
                         {"player": "Michael Penix", "likelihood": 0.5}],
        "LoochCarluccio": [{"player": "Keon Coleman", "likelihood": 0.55}],
    }
    return contention_report(targets, order, rivals, andrew="andrewroth32",
                             mode="both", roster_spots_open=0)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "--demo" in argv:
        print(json.dumps(_demo(), indent=2))
        return 0
    with open(argv[0]) as fh:
        payload = json.load(fh)
    print(json.dumps(contention_report(
        payload.get("targets", []),
        payload.get("priority_order"),
        payload.get("rival_claims"),
        andrew=payload.get("andrew"),
        andrew_priority=payload.get("andrew_priority"),
        mode=payload.get("mode", "rolling_priority"),
        budgets=payload.get("budgets"),
        roster_spots_open=payload.get("roster_spots_open", 0),
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
