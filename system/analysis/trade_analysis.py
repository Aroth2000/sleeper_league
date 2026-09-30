#!/usr/bin/env python3
"""trade_analysis.py -- deterministic trade finder for the Sunday Scaries Tuesday brief.

WHAT IT DOES
  Reads the raw Sleeper files the weekly run already fetches (rosters, users,
  matchups_week*.json) plus the 2026 draft picks file, builds a rest-of-season
  (ROS) value for every rostered player, and then searches every trade Andrew
  could make with each of the nine rivals.

  A trade is scored by the one thing that wins fantasy leagues: how many more
  points each side's OPTIMAL STARTING LINEUP scores over the remaining weeks,
  with bye weeks and injuries accounted for week by week. Then it checks
  whether the other owner would plausibly say yes.

WHAT IT DOES NOT DO
  It does not read the news. Injuries, role changes and suspensions come in
  through an optional flags file that the research step fills in (see FLAGS
  below), and `flag_candidates` in the output lists exactly who to research.
  The Tuesday brief runs this script twice: once to find the candidates, then
  again after the research step writes the flags.

  Numbers are heuristics, not projections. ppg is a shrunk blend of what the
  player has actually scored this season and a prior from where he was drafted.
  Every tunable constant is at the top of the file.

USAGE (from the system/ directory)
  python3 analysis/trade_analysis.py --raw raw --me 2 \
      --flags state/week_4_flags.json --out state/week_4_trades.json \
      --md reports/week_4_trades.md

FLAGS  (optional JSON, keyed by Sleeper player_id)
  {"9493": {"note": "hip, McVay unsure Wk3", "out_weeks": [4, 5]},
   "8151": {"ros_mult": 1.05, "note": "locked-in RB1"},
   "13281": {"out_through": 6, "note": "IR, back ~Wk7"},
   "5850": {"season_ending": true, "note": "exempt list, no return date"},
   "9997": {"ppg_override": 17.0},
   "8134": {"untouchable": true},
   "9500": {"team": "TEN"}}
  out_weeks     : specific weeks he will miss (added to his bye)
  out_through   : misses every week up to and including this one
  season_ending : misses every remaining week
  ros_mult      : scales his ROS ppg (role gain/loss); ppg_override replaces it
  untouchable   : never offered by Andrew
  team          : corrects a stale NFL team (used for bye weeks)
"""
import argparse
import glob
import json
import math
import os
import re
import sys
from collections import defaultdict

try:  # run as a script from system/, or imported from the analysis directory
    import keeper_equity as KE
except ImportError:  # pragma: no cover
    from analysis import keeper_equity as KE

# --------------------------------------------------------------------------
# Tunable constants
# --------------------------------------------------------------------------

STARTER_SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX"]  # DEF is not traded
FLEX_POS = {"RB", "WR", "TE"}
SF_POS = {"QB", "RB", "WR", "TE"}
TRADEABLE_POS = {"QB", "RB", "WR", "TE"}

# What a free-agent pickup scores. Also fills an empty slot / bye-week hole.
REPLACEMENT_PPG = {"QB": 11.0, "RB": 7.0, "WR": 7.0, "TE": 5.0}

# A player kept in the 2026 draft sits in a late round because of his keeper
# COST, not his talent. Floor his prior so Bo Nix (kept R11) is not treated as
# a round-11 QB.
KEPT_PRIOR_FLOOR = {"QB": 16.0, "RB": 12.0, "WR": 12.0, "TE": 9.0}

# How many games of evidence the draft-round prior is worth. Higher = trust
# pedigree longer, lower = trust this season's box scores sooner.
PRIOR_GAMES = 3.0

# Playoff weeks count for less: not every team gets there, and lineups are
# less certain. 6 of 10 teams make the playoffs.
PLAYOFF_WEIGHT = 0.5

# Perceived-value multiplier when an owner judges a trade. Superflex QBs are
# scarce; TEs are streamable.
MARKET_POS_MULT = {"QB": 1.15, "RB": 1.0, "WR": 1.0, "TE": 0.85}

ROSTER_ACTIVE_LIMIT = 15  # non-IR players, DEF included
IR_DEFAULT_OUT_WEEKS = 4   # an IR player with no flag is assumed out this long

# Trade acceptance filters
MIN_MY_GAIN = 4.0          # weighted ROS points; ~0.35 pts/week over the rest of the year
MIN_PARTNER_GAIN = -1.0    # they may not lose lineup points
MIN_PV_RATIO = 0.85        # they must receive >= 85% of the perceived value they give up
WIN_WIN_PARTNER_GAIN = 0.5
WIN_WIN_RATIO_RANGE = (0.90, 1.30)
MAX_PACKAGE_POOL = 9       # candidate players per side considered for 2-for-1s
# Chance any one starter is unavailable in a given week (injury, illness, rest).
# Used to price DEPTH: giving two starters for one looks free until somebody
# gets hurt, so every lineup is scored net of this first-order injury loss.
WEEKLY_ABSENCE_RATE = 0.10
# Straight swaps the brief always reports on, as "give>get" position pairs.
DEFAULT_SWAPS = ("RB>WR", "WR>RB")
TOP_TRADES_PER_PARTNER = 3


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------

class Snapshot(object):
    """Everything the analysis needs, in plain dicts (easy to build in tests)."""

    def __init__(self, rosters, players, points, byes, weeks_played,
                 reg_last=14, last_week=17, trade_deadline=13, config=None):
        self.rosters = rosters            # {rid: {owner, team, players, reserve, wins, losses, fpts}}
        self.players = players            # {pid: {name, pos, team, draft_round, kept}}
        self.points = points              # {pid: {week: pts}}
        self.byes = byes                  # {TEAM: week}
        self.weeks_played = sorted(weeks_played)
        self.reg_last = reg_last
        self.last_week = last_week
        self.trade_deadline = trade_deadline
        self.config = config or {}

    @property
    def from_week(self):
        return (max(self.weeks_played) + 1) if self.weeks_played else 1

    def horizon(self):
        return list(range(self.from_week, self.last_week + 1))

    def weight(self, week):
        return 1.0 if week <= self.reg_last else PLAYOFF_WEIGHT


class Player(object):
    def __init__(self, pid, name, pos, team, ppg, prior, obs_mean, n_obs,
                 avail, is_ir=False, note=None, draft_round=None, kept=False,
                 untouchable=False, missed=0, pv=0.0):
        self.pid = pid
        self.name = name
        self.pos = pos
        self.team = team
        self.ppg = ppg
        self.prior = prior
        self.obs_mean = obs_mean
        self.n_obs = n_obs
        self.avail = avail          # {week: bool}
        self.is_ir = is_ir
        self.note = note
        self.draft_round = draft_round
        self.kept = kept
        self.untouchable = untouchable
        self.missed = missed        # zero-point weeks so far (DNP / inactive / bye)
        self.pv = pv                # perceived market value

    def to_dict(self):
        return {"pid": self.pid, "name": self.name, "pos": self.pos, "team": self.team,
                "ppg": round(self.ppg, 2), "prior": round(self.prior, 2),
                "obs_mean": None if self.obs_mean is None else round(self.obs_mean, 2),
                "games": self.n_obs, "missed": self.missed, "ir": self.is_ir, "note": self.note}


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def _read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return default


def _load_picks(path):
    """Accepts the compact form {pid: [name,pos,team,round,is_keeper]} or a raw
    Sleeper /draft/{id}/picks list."""
    data = _read_json(path, {})
    out = {}
    if isinstance(data, dict):
        for pid, v in data.items():
            if isinstance(v, (list, tuple)) and len(v) >= 5:
                out[str(pid)] = {"name": v[0], "pos": v[1], "team": v[2],
                                 "round": int(v[3]), "kept": bool(v[4])}
    elif isinstance(data, list):
        for pk in data:
            md = pk.get("metadata") or {}
            pid = str(pk.get("player_id"))
            out[pid] = {"name": ("%s %s" % (md.get("first_name", ""), md.get("last_name", ""))).strip(),
                        "pos": md.get("position"), "team": md.get("team"),
                        "round": int(pk.get("round") or 0), "kept": bool(pk.get("is_keeper"))}
    return out


def _load_player_index(raw_dir, system_dir):
    """id -> {name, pos, team} from the player cache and resolved-player files."""
    idx = {}
    cache = _read_json(os.path.join(system_dir, "players_cache.json"), {})
    for pid, p in ((cache or {}).get("players") or {}).items():
        idx[str(pid)] = {"name": p.get("name") or ("%s %s" % (p.get("first_name", ""), p.get("last_name", ""))).strip(),
                         "pos": p.get("pos") or p.get("position"), "team": p.get("team")}
    path = os.path.join(raw_dir, "players_resolved.jsonl")
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    p = json.loads(line)
                except ValueError:
                    continue
                pid = str(p.get("player_id") or "")
                if pid:
                    idx[pid] = {"name": p.get("full_name") or ("%s %s" % (p.get("first_name", ""), p.get("last_name", ""))).strip(),
                                "pos": p.get("position") or p.get("pos"), "team": p.get("team")}
    return idx


def load_snapshot(raw_dir, config_path=None, system_dir=None):
    system_dir = system_dir or os.path.join(raw_dir, "..")
    config_path = config_path or os.path.join(system_dir, "league_config.json")
    cfg = _read_json(config_path, {}) or {}

    users = _read_json(os.path.join(raw_dir, "users.json"), []) or []
    by_owner = {}
    for u in users:
        md = u.get("metadata") or {}
        by_owner[str(u.get("user_id"))] = {"name": u.get("display_name"),
                                           "team": md.get("team_name") or u.get("display_name")}

    rosters = {}
    for r in _read_json(os.path.join(raw_dir, "rosters.json"), []) or []:
        rid = int(r["roster_id"])
        st = r.get("settings") or {}
        own = by_owner.get(str(r.get("owner_id")), {})
        rosters[rid] = {"owner": own.get("name") or ("roster %d" % rid),
                        "team": own.get("team") or ("roster %d" % rid),
                        "players": [str(p) for p in (r.get("players") or [])],
                        "reserve": [str(p) for p in (r.get("reserve") or [])],
                        "wins": st.get("wins", 0), "losses": st.get("losses", 0),
                        "ties": st.get("ties", 0),
                        "fpts": float(st.get("fpts", 0)) + float(st.get("fpts_decimal", 0)) / 100.0}

    picks = _load_picks(os.path.join(raw_dir, "draft_2026_picks.json"))
    index = _load_player_index(raw_dir, system_dir)
    players = {}
    all_ids = set(pid for r in rosters.values() for pid in r["players"])
    for pid in all_ids:
        base = dict(index.get(pid, {}))
        pk = picks.get(pid)
        if pk:
            base.setdefault("name", pk["name"])
            base["name"] = base.get("name") or pk["name"]
            base["pos"] = base.get("pos") or pk["pos"]
            base["team"] = base.get("team") or pk["team"]
            base["draft_round"] = pk["round"]
            base["kept"] = pk["kept"]
        if re.match(r"^[A-Z]{2,3}$", pid):  # a team defense
            base.update({"name": base.get("name") or pid, "pos": "DEF", "team": pid})
        players[pid] = base

    points = defaultdict(dict)
    weeks = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "matchups_week*.json"))):
        m = re.search(r"matchups_week(\d+)\.json$", path)
        if not m:
            continue
        wk = int(m.group(1))
        data = _read_json(path, []) or []
        if not any((row.get("points") or 0) for row in data):
            continue  # a future week Sleeper has scaffolded with all zeros
        weeks.append(wk)
        for row in data:
            for pid, pts in (row.get("players_points") or {}).items():
                points[str(pid)][wk] = float(pts)

    cal = cfg.get("calendar") or {}
    byes = ((cfg.get("nfl_bye_weeks_2026") or {}).get("byes")) or {}
    playoff_weeks = cal.get("playoff_weeks") or [15, 16, 17]
    return Snapshot(rosters, players, dict(points), byes, weeks,
                    reg_last=cal.get("last_regular_season_week", 14),
                    last_week=max(playoff_weeks),
                    trade_deadline=cal.get("trade_deadline_week", 13), config=cfg)


# --------------------------------------------------------------------------
# Player values
# --------------------------------------------------------------------------

def prior_ppg(pos, draft_round, kept=False):
    """Expected ppg for a player drafted in this round, from the same market
    table the keeper module uses (so the two never disagree)."""
    table = KE.MARKET_ROUND_BY_PPG.get(pos)
    repl = REPLACEMENT_PPG.get(pos, 7.0)
    if not table or draft_round is None:
        return repl + 0.5  # never drafted: a waiver pickup
    val = repl
    for thr, rnd in table:  # descending thresholds
        if rnd >= draft_round:
            val = thr if thr > 0 else repl
            break
    if kept:
        val = max(val, KEPT_PRIOR_FLOOR.get(pos, val))
    return max(val, repl)


def _missed_weeks(snap, pid, flags, is_ir):
    f = flags.get(pid, {})
    out = set(int(w) for w in f.get("out_weeks", []))
    if f.get("season_ending"):
        out.update(snap.horizon())
    if f.get("out_through") is not None:
        out.update(range(snap.from_week, int(f["out_through"]) + 1))
    elif is_ir and not f.get("season_ending") and "out_weeks" not in f:
        out.update(range(snap.from_week, snap.from_week + IR_DEFAULT_OUT_WEEKS))
    return out


def build_player(snap, pid, flags, is_ir=False):
    info = snap.players.get(pid, {})
    pos = info.get("pos") or "?"
    f = flags.get(pid, {})
    team = f.get("team") or info.get("team")
    rnd = info.get("draft_round")
    kept = bool(info.get("kept"))
    prior = prior_ppg(pos, rnd, kept)

    weekly = snap.points.get(pid, {})
    played = [v for w, v in weekly.items() if w in snap.weeks_played and v != 0.0]
    missed = sum(1 for w, v in weekly.items() if w in snap.weeks_played and v == 0.0)
    n = len(played)
    mean = (sum(played) / n) if n else None
    ppg = ((n * mean + PRIOR_GAMES * prior) / (n + PRIOR_GAMES)) if n else prior
    if "ppg_override" in f:
        ppg = float(f["ppg_override"])
    ppg *= float(f.get("ros_mult", 1.0))

    bye = snap.byes.get(team)
    out = _missed_weeks(snap, pid, flags, is_ir)
    avail = {}
    for w in snap.horizon():
        avail[w] = not (w == bye or w in out)

    horizon_w = sum(snap.weight(w) for w in snap.horizon()) or 1.0
    avail_frac = sum(snap.weight(w) for w, ok in avail.items() if ok) / horizon_w
    pv = MARKET_POS_MULT.get(pos, 1.0) * (0.5 * prior + 0.5 * ppg)
    pv *= 1.0 - 0.5 * (1.0 - avail_frac)  # owners only half-discount an injury

    return Player(pid, info.get("name") or pid, pos, team, ppg, prior, mean, n, avail,
                  is_ir=is_ir, note=f.get("note"), draft_round=rnd, kept=kept,
                  untouchable=bool(f.get("untouchable")), missed=missed, pv=pv)


# --------------------------------------------------------------------------
# Lineups
# --------------------------------------------------------------------------

def lineup_points(pool):
    """Best legal starting lineup from [(ppg, pos), ...]. Empty slots score the
    replacement level (you can always pick someone up). Returns (points, used_idx)."""
    order = sorted(range(len(pool)), key=lambda i: -pool[i][0])
    used = set()
    total = 0.0
    for slot_pos in ("QB", "RB", "RB", "WR", "WR", "TE"):
        pick = None
        for i in order:
            if i not in used and pool[i][1] == slot_pos:
                pick = i
                break
        if pick is None:
            total += REPLACEMENT_PPG[slot_pos]
        else:
            used.add(pick)
            total += pool[pick][0]
    # SUPER_FLEX first (it may take a QB), then FLEX -- same total either way.
    for eligible, repl in ((SF_POS, REPLACEMENT_PPG["RB"]), (FLEX_POS, REPLACEMENT_PPG["RB"])):
        pick = None
        for i in order:
            if i not in used and pool[i][1] in eligible:
                pick = i
                break
        if pick is None:
            total += repl
        else:
            used.add(pick)
            total += pool[pick][0]
    return total, used


def roster_value(players, snap, want_starts=False, injury_adjust=True):
    """Weighted ROS lineup points, week by week. players: list[Player].

    With injury_adjust (default) each week's score is reduced by the expected loss
    from any ONE starter being out: rate x (lineup - lineup without him). A deep
    roster loses little; a thin one loses a lot. That is what makes depth count."""
    total = 0.0
    per_week = {}
    starts = defaultdict(float)
    for w in snap.horizon():
        idx = [p for p in players if p.avail.get(w, True) and p.pos in TRADEABLE_POS]
        pool = [(p.ppg, p.pos) for p in idx]
        pts, used = lineup_points(pool)
        if injury_adjust and WEEKLY_ABSENCE_RATE:
            loss = 0.0
            for i in used:
                without = pool[:i] + pool[i + 1:]
                loss += pts - lineup_points(without)[0]
            pts -= WEEKLY_ABSENCE_RATE * loss
        per_week[w] = pts
        total += snap.weight(w) * pts
        if want_starts:
            for i in used:
                starts[idx[i].pid] += snap.weight(w)
    if want_starts:
        return total, per_week, starts
    return total, per_week


# --------------------------------------------------------------------------
# Team model
# --------------------------------------------------------------------------

def build_teams(snap, flags):
    teams = {}
    for rid, r in snap.rosters.items():
        plist = []
        for pid in r["players"]:
            info = snap.players.get(pid, {})
            if info.get("pos") == "DEF":
                continue
            plist.append(build_player(snap, pid, flags, is_ir=(pid in r["reserve"])))
        teams[rid] = plist
    return teams


def _percentile(vals, q):
    vals = sorted(vals)
    if not vals:
        return 0.0
    k = (len(vals) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return vals[lo] if lo == hi else vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def team_summaries(snap, teams):
    """Per-team ROS value, positional need, and spare (tradeable) players."""
    by_pos = defaultdict(list)
    for plist in teams.values():
        for p in plist:
            by_pos[p.pos].append(p.ppg)
    phantom = {pos: _percentile(v, 0.75) for pos, v in by_pos.items() if pos in TRADEABLE_POS}
    median = {pos: _percentile(v, 0.5) for pos, v in by_pos.items() if pos in TRADEABLE_POS}

    out = {}
    for rid, plist in teams.items():
        base, per_week, starts = roster_value(plist, snap, want_starts=True)
        horizon_w = sum(snap.weight(w) for w in snap.horizon()) or 1.0
        needs = {}
        for pos, ppg in phantom.items():
            fake = Player("_phantom", "phantom", pos, None, ppg, ppg, None, 0,
                          dict((w, True) for w in snap.horizon()))
            needs[pos] = round(roster_value(plist + [fake], snap)[0] - base, 1)
        spare = []
        for p in plist:
            share = starts.get(p.pid, 0.0) / horizon_w
            if share < 0.35 and p.ppg >= median.get(p.pos, 99) and not p.is_ir:
                spare.append({"pid": p.pid, "name": p.name, "pos": p.pos, "ppg": round(p.ppg, 1),
                              "starts_share": round(share, 2)})
        r = snap.rosters[rid]
        out[rid] = {"owner": r["owner"], "team": r["team"], "record": "%s-%s" % (r["wins"], r["losses"]),
                    "fpts": round(r["fpts"], 1), "ros_value": round(base, 1),
                    "need": needs, "spare": sorted(spare, key=lambda s: -s["ppg"]),
                    "starts": dict(starts)}
    return out


def standings_posture(snap, me):
    order = sorted(snap.rosters.items(),
                   key=lambda kv: (-(kv[1]["wins"] + 0.5 * kv[1].get("ties", 0)), -kv[1]["fpts"]))
    rank = [rid for rid, _ in order].index(me) + 1
    playoff_line = 6
    weeks_left = max(0, snap.reg_last - max(snap.weeks_played or [0]))
    r = snap.rosters[me]
    if rank <= 3:
        label = "contender"
    elif rank <= playoff_line:
        label = "in the hunt"
    else:
        label = "chasing"
    return {"rank": rank, "of": len(order), "record": "%s-%s" % (r["wins"], r["losses"]),
            "label": label, "regular_season_weeks_left": weeks_left,
            "trade_deadline_week": snap.trade_deadline,
            "weeks_until_deadline": max(0, snap.trade_deadline - snap.from_week + 1)}


# --------------------------------------------------------------------------
# Keepers
# --------------------------------------------------------------------------

def keeper_line(p, rules):
    """2027 keeper cost + surplus for one player."""
    if p.draft_round is None:
        rec = {"acquisition": "waiver"}
    elif p.kept:
        rec = {"acquisition": "keeper", "kept_at_round": p.draft_round, "consecutive_years_kept": 1}
    else:
        rec = {"acquisition": "draft", "draft_round": p.draft_round}
    kc = KE.keeper_cost(rec, rules)
    mkt = KE.market_round(p.pos, projected_ppg=p.ppg)
    surplus = None if not kc["eligible"] else (kc["cost_round"] - mkt)
    return {"eligible": kc["eligible"], "cost_round": kc["cost_round"], "market_round": mkt,
            "surplus_rounds": surplus, "final_year": kc["is_final_eligible_year"],
            "why_not": kc["ineligible_reason"]}


def _keeper_text(p, k):
    if not k["eligible"]:
        return "%s: not keepable in 2027 (%s)" % (p.name, (k["why_not"] or "ineligible").split(" -- ")[0])
    s = k["surplus_rounds"]
    tag = "+%d rounds of value" % s if s > 0 else ("fair" if s == 0 else "%d rounds overpriced" % s)
    fin = ", final year" if k["final_year"] else ""
    return "%s: keeps at R%d (market R%d, %s%s)" % (p.name, k["cost_round"], k["market_round"], tag, fin)


# --------------------------------------------------------------------------
# Trade search
# --------------------------------------------------------------------------

def _active_count(plist, r):
    return sum(1 for p in plist if not p.is_ir) + 1  # +1 for the team defense


def _apply(plist, give, get):
    gone = set(p.pid for p in give)
    return [p for p in plist if p.pid not in gone] + list(get)


def _forced_drop(plist, snap):
    """If a roster is over the limit after a trade, drop the player whose loss
    costs the least lineup value. Returns (new_list, dropped_or_None)."""
    if _active_count(plist, None) <= ROSTER_ACTIVE_LIMIT:
        return plist, None
    droppable = [p for p in plist if not p.is_ir]
    best = None
    for p in droppable:
        rest = [q for q in plist if q.pid != p.pid]
        val = roster_value(rest, snap)[0]
        if best is None or val > best[0]:
            best = (val, p, rest)
    return best[2], best[1]


def _pool(plist, limit):
    cand = [p for p in plist if p.pos in TRADEABLE_POS and not p.is_ir]
    cand.sort(key=lambda p: -p.pv)
    return cand[:limit]


def _packages(pool, max_size=2):
    out = [(p,) for p in pool]
    if max_size >= 2:
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                out.append((pool[i], pool[j]))
    return out


def _net_positions(give, get):
    """Positions the PARTNER gains on net (they receive `give`, send `get`)."""
    cnt = defaultdict(int)
    for p in give:
        cnt[p.pos] += 1
    for p in get:
        cnt[p.pos] -= 1
    return [pos for pos, n in cnt.items() if n > 0]


def _format_trade(t, snap, summaries, rules):
    need = summaries[t["partner_rid"]]["need"]
    why = []
    for pos in _net_positions(t["give"], t["get"]):
        if need.get(pos, 0) >= 10:
            why.append("thin at %s (a starter there is worth +%.0f pts to them)" % (pos, need[pos]))
    if not why:
        why.append("upgrades their lineup by %+.0f ROS pts" % t["partner_gain"])
    risks = []
    for p in list(t["get"]):
        bits = []
        if p.missed:
            bits.append("%d zero-point week(s) so far" % p.missed)
        if p.note:
            bits.append(p.note)
        out_wk = [w for w, ok in p.avail.items() if not ok and w != snap.byes.get(p.team)]
        if out_wk:
            bits.append("out wk %s" % (",".join(str(w) for w in out_wk[:6])))
        if bits:
            risks.append("%s: %s" % (p.name, "; ".join(bits)))
    for p in list(t["give"]):
        if p.obs_mean is not None and p.obs_mean > p.prior + 4:
            risks.append("%s is running hot (%.1f ppg vs %.1f expected) -- selling high" % (p.name, p.obs_mean, p.prior))
    keeper = [_keeper_text(p, keeper_line(p, rules)) for p in list(t["get"]) + list(t["give"])]
    moves = []
    if t["my_drop"] is not None:
        moves.append("You would need to drop %s." % t["my_drop"].name)
    if t["their_drop"] is not None:
        moves.append("They would need to drop %s." % t["their_drop"].name)
    weeks = max(1.0, sum(snap.weight(w) for w in snap.horizon()))
    return {
        "tier": t["tier"], "partner": t["partner"], "partner_team": t["partner_team"],
        "partner_rid": t["partner_rid"],
        "shape": "%d-for-%d" % (len(t["give"]), len(t["get"])),
        "give": [p.to_dict() for p in t["give"]], "get": [p.to_dict() for p in t["get"]],
        "my_ros_gain": round(t["my_gain"], 1),
        "my_ros_gain_per_week": round(t["my_gain"] / weeks, 2),
        "partner_ros_gain": round(t["partner_gain"], 1),
        "value_ratio_they_receive_vs_give": round(t["pv_ratio"], 2),
        "fairness": _fairness(t["pv_ratio"]),
        "playoff_weeks_delta": round(t["playoff_delta"], 1),
        "weekly_delta": t["weekly_delta"],
        "why_they_say_yes": why, "risks": risks, "keeper_2027": keeper, "roster_moves": moves,
    }


def find_trades(snap, teams, summaries, me, top=12, swaps=DEFAULT_SWAPS):
    """Returns (top_trades, swap_sections, my_base_value).

    top_trades   : best overall, strict filters (you gain >= MIN_MY_GAIN, they don't lose)
    swap_sections: {"RB>WR": [...], "WR>RB": [...]} best straight 1-for-1s per
                   position pair, with looser filters so an honest 'nothing works'
                   is distinguishable from 'nothing exists'."""
    mine = teams[me]
    my_base, my_weeks = roster_value(mine, snap)
    my_give_pool = [p for p in mine if p.pos in TRADEABLE_POS and not p.untouchable and not p.is_ir]
    my_give_pool.sort(key=lambda p: -p.pv)
    my_give_pool = my_give_pool[:MAX_PACKAGE_POOL + 3]
    sysdir = getattr(snap, "system_dir", None)
    rules = KE.load_rules(os.path.join(sysdir, "league_config.json")) if sysdir else KE.load_rules()

    found = []
    for rid, theirs in teams.items():
        if rid == me:
            continue
        th_base, th_weeks = roster_value(theirs, snap)
        their_pool = _pool(theirs, MAX_PACKAGE_POOL)
        for give in _packages(my_give_pool):
            for get in _packages(their_pool):
                if len(give) == 2 and len(get) == 2:
                    continue  # 2-for-2 rarely adds anything a 1-for-1 doesn't
                pv_out = sum(p.pv for p in give)   # what I send them
                pv_in = sum(p.pv for p in get)     # what they send me
                if pv_in <= 0 or pv_out / pv_in < MIN_PV_RATIO or pv_out / pv_in > 1.6:
                    continue
                new_mine, my_drop = _forced_drop(_apply(mine, give, get), snap)
                new_theirs, their_drop = _forced_drop(_apply(theirs, get, give), snap)
                my_after, my_after_weeks = roster_value(new_mine, snap)
                th_after, th_after_weeks = roster_value(new_theirs, snap)
                my_gain = my_after - my_base
                p_gain = th_after - th_base
                if my_gain <= 0 or p_gain < MIN_PARTNER_GAIN:
                    continue
                ratio = pv_out / pv_in
                win_win = (p_gain >= WIN_WIN_PARTNER_GAIN and
                           WIN_WIN_RATIO_RANGE[0] <= ratio <= WIN_WIN_RATIO_RANGE[1])
                weekly = dict((w, round(my_after_weeks[w] - my_weeks[w], 1)) for w in snap.horizon())
                found.append({
                    "partner_rid": rid, "partner": summaries[rid]["owner"],
                    "partner_team": summaries[rid]["team"], "tier": "A" if win_win else "B",
                    "give": give, "get": get, "my_gain": my_gain, "partner_gain": p_gain,
                    "pv_ratio": ratio, "weekly_delta": weekly,
                    "playoff_delta": sum(v for w, v in weekly.items() if w > snap.reg_last),
                    "my_drop": my_drop, "their_drop": their_drop,
                    "score": my_gain * (1.0 if win_win else 0.65),
                })

    found.sort(key=lambda t: -t["score"])
    strict = [t for t in found if t["my_gain"] >= MIN_MY_GAIN]
    per_partner = defaultdict(int)
    seen_give = defaultdict(int)
    picked = []
    for t in strict:
        key = tuple(sorted(p.pid for p in t["give"]))
        if per_partner[t["partner_rid"]] >= TOP_TRADES_PER_PARTNER or seen_give[key] >= 3:
            continue
        per_partner[t["partner_rid"]] += 1
        seen_give[key] += 1
        picked.append(t)
        if len(picked) >= top:
            break

    sections = {}
    for pair in swaps:
        give_pos, get_pos = pair.split(">")
        rows = [t for t in found if len(t["give"]) == 1 and len(t["get"]) == 1
                and t["give"][0].pos == give_pos and t["get"][0].pos == get_pos]
        sections[pair] = [_format_trade(t, snap, summaries, rules) for t in rows[:4]]
    return [_format_trade(t, snap, summaries, rules) for t in picked], sections, my_base


def _fairness(ratio):
    """ratio = perceived value they RECEIVE / perceived value they GIVE UP."""
    if ratio < WIN_WIN_RATIO_RANGE[0]:
        return "Leans your way on paper (they get %.0f%% of what they give up) -- expect a counter." % (ratio * 100)
    if ratio > WIN_WIN_RATIO_RANGE[1]:
        return "Leans their way on paper (they get %.0f%% of what they give up) -- you are paying for the lineup fit." % (ratio * 100)
    return "Roughly even on paper (they get %.0f%% of what they give up)." % (ratio * 100)


def watchlist(snap, teams, me):
    """Buy-low (cold or hurt vs. pedigree, not mine) and sell-high (hot, mine)."""
    buy, sell = [], []
    for rid, plist in teams.items():
        for p in plist:
            if p.pos not in TRADEABLE_POS or p.is_ir:
                continue
            if rid != me and p.n_obs + p.missed >= 1 and p.ppg < p.prior - 1.5 and p.prior >= 11:
                buy.append((p.prior - p.ppg, p, rid))
            if rid == me and p.obs_mean is not None and p.obs_mean > p.prior + 4 and p.n_obs >= 2:
                sell.append((p.obs_mean - p.prior, p, rid))
    buy.sort(key=lambda t: -t[0])
    sell.sort(key=lambda t: -t[0])

    def fmt(rows, owner):
        return [{"name": p.name, "pos": p.pos, "owner": snap.rosters[rid]["owner"] if owner else "you",
                 "ppg_now": round(p.ppg, 1), "expected_ppg": round(p.prior, 1),
                 "games": p.n_obs, "zero_weeks": p.missed, "note": p.note} for _, p, rid in rows[:8]]
    return {"buy_low": fmt(buy, True), "sell_high": fmt(sell, False)}


def flag_candidates(snap, teams):
    """Who the research step must look up before the numbers can be trusted."""
    out = []
    for rid, plist in teams.items():
        for p in plist:
            reasons = []
            if p.is_ir:
                reasons.append("on IR -- need a return date")
            if p.missed and p.n_obs >= 1:
                reasons.append("%d zero-point week(s) after playing -- injury? suspension?" % p.missed)
            if p.n_obs == 0 and p.pos in TRADEABLE_POS and (p.draft_round or 99) <= 9:
                reasons.append("no points recorded in %d weeks -- inactive?" % len(snap.weeks_played))
            if reasons:
                out.append({"pid": p.pid, "name": p.name, "pos": p.pos, "team": p.team,
                            "owner": snap.rosters[rid]["owner"], "reasons": reasons})
    return out


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _names(plist):
    return " + ".join("%s (%s, %.1f ppg)" % (p["name"], p["pos"], p["ppg"]) for p in plist)


def render_markdown(result):
    L = []
    me = result["me"]
    post = result["posture"]
    L.append("# Trade board")
    L.append("")
    if result.get("unresolved_player_ids"):
        L.append("> **WARNING:** %d rostered player(s) could not be identified (ids: %s) and are missing "
                 "from every lineup below. Fetch /players/nfl/{id} for each, append to raw/players_resolved.jsonl, "
                 "and re-run before trusting these numbers." % (
                     len(result["unresolved_player_ids"]), ", ".join(result["unresolved_player_ids"])))
        L.append("")
    L.append("*Week %s. You are %s (%s, rank %d of %d). %d week(s) until the Week %d trade deadline.*" % (
        result["week"], me["owner"], post["record"], post["rank"], post["of"],
        post["weeks_until_deadline"], post["trade_deadline_week"]))
    L.append("")
    L.append("Numbers are rest-of-season *lineup points*: how many more points each side's best "
             "starting lineup scores through the fantasy playoffs, week by week, with byes and "
             "injuries removed. Tier A = both sides gain and the swap is close to even in perceived "
             "value. Tier B = you gain and they don't lose, but it's lopsided enough that they may push back.")
    L.append("")
    def block(i, t):
        L.append("## %s [Tier %s, %s] with %s (%s)" % (i, t["tier"], t["shape"], t["partner"], t["partner_team"]))
        L.append("- **You give:** %s" % _names(t["give"]))
        L.append("- **You get:** %s" % _names(t["get"]))
        L.append("- **You:** %+.1f ROS lineup pts (%+.2f/wk). **Them:** %+.1f. Playoff weeks alone: %+.1f for you." % (
            t["my_ros_gain"], t["my_ros_gain_per_week"], t["partner_ros_gain"], t["playoff_weeks_delta"]))
        L.append("- **Fairness:** %s" % t["fairness"])
        L.append("- **Why they say yes:** %s" % "; ".join(t["why_they_say_yes"]))
        if t["risks"]:
            L.append("- **Risks:** %s" % " | ".join(t["risks"]))
        L.append("- **2027 keepers:** %s" % " | ".join(t["keeper_2027"]))
        if t["roster_moves"]:
            L.append("- **Roster moves:** %s" % " ".join(t["roster_moves"]))
        L.append("")

    L.append("# Best trades, any shape")
    L.append("")
    if not result["trades"]:
        L.append("No trade cleared the filters this week. That is a real answer: your roster and each "
                 "rival's are already well matched, so do not force one.")
        L.append("")
    for i, t in enumerate(result["trades"], 1):
        block(i, t)
    for pair, rows in (result.get("swaps") or {}).items():
        give_pos, get_pos = pair.split(">")
        L.append("# Straight swaps: your %s for their %s" % (give_pos, get_pos))
        L.append("")
        if not rows:
            L.append("No one-for-one %s-for-%s swap adds lineup points for you without costing the other side. "
                     "That usually means you are not actually short at %s, or the market prices the swap "
                     "against you." % (give_pos, get_pos, get_pos))
            L.append("")
        for i, t in enumerate(rows, 1):
            block("%s%d" % (give_pos[0].lower(), i), t)
    wl = result["watchlist"]
    if wl["buy_low"]:
        L.append("## Buy-low watchlist")
        for w in wl["buy_low"]:
            L.append("- %s (%s, %s): %.1f ppg now vs %.1f expected%s" % (
                w["name"], w["pos"], w["owner"], w["ppg_now"], w["expected_ppg"],
                (" -- " + w["note"]) if w["note"] else ""))
        L.append("")
    if wl["sell_high"]:
        L.append("## Sell-high (yours)")
        for w in wl["sell_high"]:
            L.append("- %s (%s): %.1f ppg vs %.1f expected" % (w["name"], w["pos"], w["ppg_now"], w["expected_ppg"]))
        L.append("")
    L.append("## Who needs what (points a starter-level add is worth to each team)")
    L.append("")
    L.append("| Team | Record | QB | RB | WR | TE | Spare players |")
    L.append("|---|---|---|---|---|---|---|")
    for rid, s in sorted(result["teams"].items(), key=lambda kv: int(kv[0])):
        sp = ", ".join("%s (%s)" % (x["name"], x["pos"]) for x in s["spare"][:3]) or "-"
        n = s["need"]
        L.append("| %s | %s | %.0f | %.0f | %.0f | %.0f | %s |" % (
            s["owner"], s["record"], n.get("QB", 0), n.get("RB", 0), n.get("WR", 0), n.get("TE", 0), sp))
    L.append("")
    return "\n".join(L)


def analyze(snap, me, flags=None, top=12, swaps=DEFAULT_SWAPS):
    flags = flags or {}
    teams = build_teams(snap, flags)
    summaries = team_summaries(snap, teams)
    trades, swap_sections, my_base = find_trades(snap, teams, summaries, me, top=top, swaps=swaps)
    unresolved = sorted(pid for pid, p in snap.players.items() if not p.get("pos") or not p.get("name"))
    result = {
        "week": snap.from_week,
        "me": {"rid": me, "owner": snap.rosters[me]["owner"], "ros_value": round(my_base, 1)},
        "posture": standings_posture(snap, me),
        "trades": trades,
        "swaps": swap_sections,
        "watchlist": watchlist(snap, teams, me),
        "flag_candidates": flag_candidates(snap, teams),
        "unresolved_player_ids": unresolved,
        "teams": dict((str(rid), dict((k, v) for k, v in s.items() if k != "starts"))
                      for rid, s in summaries.items()),
        "assumptions": {
            "weeks_of_data": snap.weeks_played, "horizon": [snap.from_week, snap.last_week],
            "playoff_weight": PLAYOFF_WEIGHT, "prior_games": PRIOR_GAMES,
            "replacement_ppg": REPLACEMENT_PPG,
            "notes": ["Exactly 0.0 points in a week is treated as did-not-play, not as a bad game.",
                      "Bye weeks use the player's NFL team as of the draft unless a flag corrects it.",
                      "IR players with no flag are assumed out %d more weeks." % IR_DEFAULT_OUT_WEEKS,
                      "ppg is a shrunk blend of this season's points and a draft-round prior; "
                      "it is a heuristic, not a projection."],
        },
    }
    return result


def decisions_from(result, limit=3):
    """This week's trade ideas in the season-log decisions format so next week's
    grading step can score them."""
    out = []
    for t in result["trades"][:limit]:
        out.append({"type": "trade",
                    "call": "Propose to %s: give %s for %s" % (
                        t["partner"], " + ".join(p["name"] for p in t["give"]),
                        " + ".join(p["name"] for p in t["get"])),
                    "rationale": "%+.1f ROS lineup pts for you, %+.1f for them (Tier %s)" % (
                        t["my_ros_gain"], t["partner_ros_gain"], t["tier"]),
                    "outcome": None})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", default="raw", help="directory holding the raw Sleeper files")
    ap.add_argument("--system", default=None, help="system/ directory (default: parent of --raw)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--me", type=int, default=2, help="Andrew's roster_id")
    ap.add_argument("--flags", default=None, help="JSON of research overrides")
    ap.add_argument("--out", default=None, help="write JSON here")
    ap.add_argument("--md", default=None, help="write markdown here")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--swaps", default=",".join(DEFAULT_SWAPS),
                    help="position pairs for straight 1-for-1 sections, e.g. RB>WR,WR>RB")
    ap.add_argument("--candidates-only", action="store_true",
                    help="print only the players the research step must look up")
    args = ap.parse_args(argv)

    system_dir = args.system or os.path.abspath(os.path.join(args.raw, ".."))
    snap = load_snapshot(args.raw, args.config, system_dir)
    snap.system_dir = system_dir
    flags = _read_json(args.flags, {}) if args.flags else {}
    flags = dict((str(k), v) for k, v in (flags or {}).items() if not str(k).startswith("_"))

    result = analyze(snap, args.me, flags, top=args.top,
                     swaps=tuple(x for x in args.swaps.split(",") if x))
    if args.candidates_only:
        print(json.dumps(result["flag_candidates"], indent=1))
        return 0
    text = render_markdown(result)
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(result, fh, indent=1, default=str)
    if args.md:
        with open(args.md, "w") as fh:
            fh.write(text)
    print(text)
    if result["unresolved_player_ids"]:
        sys.stderr.write("WARNING: unresolved player ids (fetch /players/nfl/{id}): %s\n"
                         % ", ".join(result["unresolved_player_ids"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
