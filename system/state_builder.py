#!/usr/bin/env python3
"""
state_builder.py -- deterministic Phase 0 of the Sunday Scaries weekly run.

Reads the raw Sleeper JSON that the WebFetch step dropped into system/raw/
(see fetch_manifest.md for the exact contract) and emits

    system/state/week_<N>.json

matching the schema in weekly_system_plan.md Part 2.

WHAT IT COMPUTES
  * meta            -- league ids, week, season phase, waiver day, provenance
  * standings       -- record, PF/PA, waiver priority, playoff seed line
  * teams           -- roster split into filled starter slots and bench,
                       positional counts, injuries, bye-week coverage
  * transaction_log -- this week's Sleeper transactions, normalised
  * roster_diff     -- add/drop/move diff computed against week_<N-1>.json
  * injuries        -- league-wide injury list from the players cache
  * bye_coverage    -- per team, per position, who is out and who covers
  * free_agents     -- every cached player id NOT on any roster (the hard gate
                       against recommending an unavailable player)
  * open_questions  -- anything the code could not establish

DESIGN RULES
  * Pure stdlib. No network. No HTTP client anywhere in this file -- the
    sandbox proxy 403s api.sleeper.app, so fetching is WebFetch's job.
  * Degrades gracefully. Every raw file is optional. A missing file produces a
    warning plus a null/empty section, never a traceback.
  * Never invents data. If a bye week is unknown it says unknown.

CLI
  python3 state_builder.py                    # infers week from raw/state_nfl.json
  python3 state_builder.py --week 7
  python3 state_builder.py --week 7 --raw-dir raw --out-dir state
  python3 state_builder.py --week 7 --summary        # human-readable printout
  python3 state_builder.py --week 7 --dry-run        # print, do not write
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW = os.path.join(HERE, "raw")
DEFAULT_STATE = os.path.join(HERE, "state")
DEFAULT_CONFIG = os.path.join(HERE, "league_config.json")

try:
    from players_cache import PlayersCache, NFL_TEAMS
except ImportError:                                  # allow running from elsewhere
    sys.path.insert(0, HERE)
    from players_cache import PlayersCache, NFL_TEAMS

# Which real positions may fill which starter slot.
SLOT_ELIGIBILITY = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}

INJURY_SEVERITY = {
    "Out": 4, "IR": 5, "PUP": 4, "Sus": 4, "NA": 4, "DNR": 5,
    "Doubtful": 3, "Questionable": 2, "Probable": 1,
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class Loader:
    """Loads optional raw files, recording what was missing instead of dying."""

    def __init__(self, raw_dir: str):
        self.raw_dir = raw_dir
        self.loaded: List[str] = []
        self.missing: List[str] = []
        self.broken: List[str] = []

    def load(self, *candidates: str, default: Any = None) -> Any:
        """Tries each candidate filename in order; returns the first that parses."""
        for name in candidates:
            path = os.path.join(self.raw_dir, name)
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read().strip()
                if not text:
                    self.broken.append(f"{name} (empty)")
                    continue
                if name.endswith(".jsonl"):
                    out = []
                    for line in text.splitlines():
                        line = line.strip().rstrip(",")
                        if line and line not in ("[", "]"):
                            try:
                                out.append(json.loads(line))
                            except ValueError:
                                pass
                    self.loaded.append(name)
                    return out
                self.loaded.append(name)
                return json.loads(text)
            except (OSError, ValueError) as exc:
                self.broken.append(f"{name} ({exc})")
        self.missing.append(candidates[0])
        return default


def _read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _season_phase(week: Optional[int], config: Dict[str, Any]) -> Dict[str, Any]:
    if week is None:
        return {"name": "unknown", "weeks": [], "default_posture": None}
    for phase in config.get("season_phases", []):
        if week in phase.get("weeks", []):
            return phase
    if week <= 0:
        return {"name": "preseason", "weeks": [],
                "default_posture": "Draft prep and keeper decisions. No lineup or waiver activity yet."}
    return {"name": "unknown", "weeks": [], "default_posture": None}


# ---------------------------------------------------------------------------
# lineup / slot filling
# ---------------------------------------------------------------------------

def split_starters_bench(roster: Dict[str, Any],
                         starter_slots: List[str],
                         pc: PlayersCache) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Map Sleeper's positional starters array onto named slots, and return the
    remainder as bench. Sleeper's starters array is index-aligned to
    roster_positions, so slot i is starter i -- but it may contain '0' for an
    empty slot and may be shorter than the slot list."""
    notes: List[str] = []
    starters_raw = list(roster.get("starters") or [])
    all_players = [p for p in (roster.get("players") or []) if p]

    if len(starters_raw) != len(starter_slots):
        notes.append(
            f"starters array length {len(starters_raw)} != {len(starter_slots)} starter slots; "
            "aligned by index and padded"
        )
    starters_raw += [None] * (len(starter_slots) - len(starters_raw))

    starters: List[Dict[str, Any]] = []
    used: List[str] = []
    for slot, pid in zip(starter_slots, starters_raw[:len(starter_slots)]):
        if not pid or pid == "0":
            starters.append({"slot": slot, "player_id": None, "name": None,
                             "pos": None, "team": None, "empty": True})
            notes.append(f"{slot} slot is EMPTY")
            continue
        rec = pc.get(pid)
        pos = rec.get("pos")
        entry = {
            "slot": slot,
            "player_id": pid,
            "name": rec.get("name"),
            "pos": pos,
            "team": rec.get("team"),
            "injury_status": rec.get("injury_status"),
            "unresolved": bool(rec.get("unresolved")),
        }
        allowed = SLOT_ELIGIBILITY.get(slot)
        if pos and allowed and pos not in allowed:
            entry["slot_mismatch"] = True
            notes.append(f"{rec.get('name') or pid} ({pos}) is in the {slot} slot, which takes {sorted(allowed)}")
        starters.append(entry)
        used.append(pid)

    bench = []
    for pid in all_players:
        if pid in used:
            continue
        rec = pc.get(pid)
        bench.append({
            "player_id": pid,
            "name": rec.get("name"),
            "pos": rec.get("pos"),
            "team": rec.get("team"),
            "injury_status": rec.get("injury_status"),
            "unresolved": bool(rec.get("unresolved")),
        })
    bench.sort(key=lambda b: (b.get("pos") or "ZZ", b.get("name") or b["player_id"]))
    return starters, bench, notes


def positional_counts(player_ids: List[str], pc: PlayersCache) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for pid in player_ids:
        pos = pc.get(pid).get("pos") or "UNKNOWN"
        counts[pos] = counts.get(pos, 0) + 1
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# bye weeks
# ---------------------------------------------------------------------------

def bye_coverage(player_ids: List[str], week: Optional[int], byes: Dict[str, int],
                 starter_ids: List[str], pc: PlayersCache) -> Dict[str, Any]:
    """Who on this roster is on bye THIS week, and does the bench cover it?"""
    if not byes:
        return {"status": "unknown",
                "reason": "league_config.nfl_bye_weeks_2026.byes is empty; cannot compute",
                "on_bye_this_week": [], "by_position": {}, "uncovered_slots": []}
    if week is None:
        return {"status": "unknown", "reason": "week unknown",
                "on_bye_this_week": [], "by_position": {}, "uncovered_slots": []}

    on_bye, by_pos, unknown_team = [], {}, []
    for pid in player_ids:
        rec = pc.get(pid)
        team = rec.get("team")
        if not team:
            unknown_team.append(pid)
            continue
        bye = byes.get(team)
        if bye is None:
            unknown_team.append(pid)
            continue
        pos = rec.get("pos") or "UNKNOWN"
        by_pos.setdefault(pos, []).append(bye)
        if bye == week:
            on_bye.append({"player_id": pid, "name": rec.get("name"),
                           "pos": pos, "team": team,
                           "is_starter": pid in starter_ids})

    uncovered = []
    for entry in on_bye:
        if not entry["is_starter"]:
            continue
        replacement = any(
            pc.get(pid).get("pos") == entry["pos"]
            and pid not in starter_ids
            and byes.get(pc.get(pid).get("team") or "") != week
            for pid in player_ids
        )
        if not replacement:
            uncovered.append(entry)

    return {
        "status": "ok",
        "on_bye_this_week": on_bye,
        "by_position": {k: sorted(set(v)) for k, v in sorted(by_pos.items())},
        "uncovered_slots": uncovered,
        "players_with_unknown_bye": unknown_team,
    }


# ---------------------------------------------------------------------------
# transactions
# ---------------------------------------------------------------------------

def normalise_transactions(txns: List[Dict[str, Any]], week: Optional[int],
                           roster_owner: Dict[int, str], pc: PlayersCache) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in txns or []:
        if not isinstance(t, dict):
            continue
        settings = t.get("settings") or {}
        rids = t.get("roster_ids") or []
        adds, drops = [], []
        for pid, rid in (t.get("adds") or {}).items():
            adds.append({"player_id": pid, "player": pc.display(pid),
                         "to_roster_id": rid, "to_team": roster_owner.get(rid)})
        for pid, rid in (t.get("drops") or {}).items():
            drops.append({"player_id": pid, "player": pc.display(pid),
                          "from_roster_id": rid, "from_team": roster_owner.get(rid)})
        out.append({
            "transaction_id": t.get("transaction_id"),
            "week": t.get("leg", week),
            "type": t.get("type"),
            "status": t.get("status"),
            "teams": [roster_owner.get(r, str(r)) for r in rids],
            "roster_ids": rids,
            "added": adds,
            "dropped": drops,
            "draft_picks": t.get("draft_picks") or [],
            # Sleeper only stamps settings.priority on waiver claims that
            # actually consumed priority. Its presence is the empirical proof
            # that this league runs priority waivers, not FAAB.
            "priority_used": settings.get("priority"),
            "seq": settings.get("seq"),
            "faab_bid": (t.get("waiver_budget") or None),
            "created_ms": t.get("created"),
            "created_utc": (datetime.datetime.fromtimestamp(t["created"] / 1000, datetime.timezone.utc)
                            .replace(microsecond=0).isoformat()) if t.get("created") else None,
            "note": (t.get("metadata") or {}).get("notes") if isinstance(t.get("metadata"), dict) else None,
        })
    out.sort(key=lambda x: (x.get("created_ms") or 0), reverse=True)
    return out


def normalise_matchups(matchups: List[Dict[str, Any]], roster_owner: Dict[int, str],
                       pc: PlayersCache) -> Dict[str, Any]:
    """Turn /matchups/{week} into head-to-head pairs plus per-player points.

    This is the factual basis for the 'performance pressure' term in the
    opponent model (plan Part 4): points a starter actually scored, and the
    bench points a manager left behind.
    """
    if not matchups:
        return {"status": "not_loaded", "pairs": [], "by_roster": {}}

    by_roster: Dict[str, Any] = {}
    for m in matchups:
        if not isinstance(m, dict):
            continue
        rid = m.get("roster_id")
        pp = m.get("players_points") or {}
        # starters_points is index-aligned to the UNFILTERED starters array.
        # Sleeper writes "0" into an unfilled starter slot -- jomud (roster 4)
        # has one right now -- so pairing must happen BEFORE the empties are
        # dropped. Filtering first shifts every subsequent starter's score onto
        # the wrong player, silently and with no error.
        raw_starters = m.get("starters") or []
        starter_pts = m.get("starters_points") or []
        paired = [
            (pid, (starter_pts[i] if i < len(starter_pts) else None))
            for i, pid in enumerate(raw_starters)
        ]
        paired = [(pid, pts) for pid, pts in paired if pid and pid != "0"]
        starters = [pid for pid, _ in paired]
        bench = [p for p in (m.get("players") or []) if p and p not in starters]
        by_roster[str(rid)] = {
            "roster_id": rid,
            "owner": roster_owner.get(rid),
            "matchup_id": m.get("matchup_id"),
            "points": m.get("points"),
            "starters": [
                {"player_id": pid, "player": pc.display(pid),
                 "points": (pts if pts is not None else pp.get(pid))}
                for pid, pts in paired
            ],
            # Points left on the bench -- the classic "should have started him"
            # signal, and a strong tell that a manager is about to churn.
            "bench_points": sorted(
                [{"player_id": pid, "player": pc.display(pid), "points": pp.get(pid, 0)}
                 for pid in bench],
                key=lambda x: -(x["points"] or 0),
            ),
        }

    pairs: Dict[Any, List[str]] = {}
    for rid, rec in by_roster.items():
        pairs.setdefault(rec.get("matchup_id"), []).append(rid)
    pair_list = []
    for mid, rids in sorted(pairs.items(), key=lambda kv: (kv[0] is None, kv[0])):
        entry = {"matchup_id": mid,
                 "teams": [{"roster_id": by_roster[r]["roster_id"],
                            "owner": by_roster[r]["owner"],
                            "points": by_roster[r]["points"]} for r in rids]}
        if len(entry["teams"]) == 2:
            a, b = entry["teams"]
            entry["winner"] = (a["owner"] if (a["points"] or 0) > (b["points"] or 0)
                               else b["owner"] if (b["points"] or 0) > (a["points"] or 0)
                               else "tie")
        pair_list.append(entry)

    return {"status": "ok", "pairs": pair_list, "by_roster": by_roster}


def roster_diff(prev_state: Optional[Dict[str, Any]],
                cur_teams: Dict[str, Any], pc: PlayersCache) -> Dict[str, Any]:
    """Diff current rosters against the previous week's state file."""
    if not prev_state:
        return {"status": "no_previous_state",
                "note": "First run, or week_N-1.json missing. Nothing to diff against.",
                "by_team": {}, "totals": {"added": 0, "dropped": 0}}

    prev_teams = prev_state.get("teams") or {}
    by_team, tot_add, tot_drop = {}, 0, 0
    for rid, team in cur_teams.items():
        cur_ids = set(team.get("players") or [])
        prev_team = prev_teams.get(rid) or {}
        prev_ids = set(prev_team.get("players") or [])
        if not prev_ids:
            by_team[rid] = {"owner": team.get("owner"), "status": "no_previous_roster",
                            "added": [], "dropped": []}
            continue
        added = sorted(cur_ids - prev_ids)
        dropped = sorted(prev_ids - cur_ids)

        prev_start = set(prev_team.get("starter_ids") or [])
        cur_start = set(team.get("starter_ids") or [])
        promoted = sorted((cur_start - prev_start) & cur_ids & prev_ids)
        benched = sorted((prev_start - cur_start) & cur_ids & prev_ids)

        tot_add += len(added)
        tot_drop += len(dropped)
        by_team[rid] = {
            "owner": team.get("owner"),
            "added": [{"player_id": p, "player": pc.display(p)} for p in added],
            "dropped": [{"player_id": p, "player": pc.display(p)} for p in dropped],
            "promoted_to_starter": [{"player_id": p, "player": pc.display(p)} for p in promoted],
            "benched": [{"player_id": p, "player": pc.display(p)} for p in benched],
            "net_change": len(added) - len(dropped),
        }
    return {
        "status": "ok",
        "vs_week": prev_state.get("meta", {}).get("week"),
        "by_team": by_team,
        "totals": {"added": tot_add, "dropped": tot_drop},
        "active_teams": sorted(
            [rid for rid, d in by_team.items() if d.get("added") or d.get("dropped")],
            key=lambda r: -(len(by_team[r].get("added", [])) + len(by_team[r].get("dropped", []))),
        ),
    }


# ---------------------------------------------------------------------------
# main build
# ---------------------------------------------------------------------------

def build(week: Optional[int], raw_dir: str, out_dir: str,
          config_path: str) -> Dict[str, Any]:
    warnings: List[str] = []
    open_questions: List[str] = []

    config = _read_json(config_path, default={}) or {}
    if not config:
        warnings.append(f"league_config.json missing or unreadable at {config_path}; "
                        "falling back to whatever the raw league payload provides")

    ld = Loader(raw_dir)
    league = ld.load("league.json", default=None)
    users = ld.load("users.json", default=[]) or []
    rosters = ld.load("rosters.json", default=[]) or []
    nfl_state = ld.load("state_nfl.json", default={}) or {}
    # Week 0 (preseason) has no matchups endpoint to speak of; asking for one
    # would pollute the missing-files list with a file that was never expected.
    matchups = ld.load(f"matchups_week{week}.json", default=[]) if week else []
    trending = ld.load("trending_add.json", default=[]) or []

    pc = PlayersCache()
    pc.seed_defenses()
    # Keep the cache honest: any id sitting on a roster is at least "seen".
    for r in rosters:
        pc.ingest_roster(r, source="rosters")

    # ---- week ----
    if week is None:
        week = nfl_state.get("week") or nfl_state.get("display_week")
        if isinstance(week, int) and week <= 0:
            warnings.append(f"Sleeper reports week {week} (preseason). "
                            "Building a preseason snapshot; there is no lineup to set yet.")
    if week is None:
        week = 0
        open_questions.append("Could not determine the current week; defaulted to 0. "
                              "Pass --week explicitly or fetch /v1/state/nfl.")

    # ---- config-derived constants, with raw-league fallback ----
    cfg_roster = config.get("roster") or {}
    starter_slots = cfg_roster.get("starter_slots")
    if not starter_slots:
        rp = (league or {}).get("roster_positions") or []
        starter_slots = [p for p in rp if p != "BN"]
        if starter_slots:
            warnings.append("starter_slots taken from raw league payload (config missing it)")
    if not starter_slots:
        starter_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "SUPER_FLEX", "DEF"]
        warnings.append("starter_slots defaulted to the known 2026 layout; verify against Sleeper")

    league_id = (config.get("league") or {}).get("league_id") or (league or {}).get("league_id")
    season = (league or {}).get("season") or (config.get("league") or {}).get("season")
    byes = ((config.get("nfl_bye_weeks_2026") or {}).get("byes")) or {}
    if not byes:
        open_questions.append(
            "2026 NFL bye weeks are not populated in league_config.json "
            "(nfl_bye_weeks_2026.byes). Bye-week coverage cannot be computed until they are. "
            "Deliberately not guessed."
        )

    # ---- transactions (accept several naming conventions) ----
    txn_raw = ld.load(f"transactions_week{week}.json",
                      f"transactions_{week}.json",
                      "transactions.json", default=None)
    if txn_raw is None:
        txn_raw = []
        if week and week > 0:
            warnings.append(f"no transactions file for week {week} "
                            f"(expected raw/transactions_week{week}.json); transaction_log will be empty")

    # ---- identity maps ----
    user_by_id = {u.get("user_id"): u for u in users if isinstance(u, dict)}
    roster_owner: Dict[int, str] = {}
    for r in rosters:
        u = user_by_id.get(r.get("owner_id")) or {}
        roster_owner[r.get("roster_id")] = u.get("display_name") or f"roster_{r.get('roster_id')}"
    if not users:
        warnings.append("users.json missing; owner display names unavailable")

    andrew_rid = (config.get("andrew") or {}).get("roster_id", 2)

    # ---- standings ----
    standings = []
    for r in rosters:
        s = r.get("settings") or {}
        rid = r.get("roster_id")
        u = user_by_id.get(r.get("owner_id")) or {}
        pf = s.get("fpts", 0) + (s.get("fpts_decimal", 0) or 0) / 100.0
        pa = s.get("fpts_against", 0) + (s.get("fpts_against_decimal", 0) or 0) / 100.0
        standings.append({
            "roster_id": rid,
            "owner": roster_owner.get(rid),
            "team_name": (u.get("metadata") or {}).get("team_name"),
            "wins": s.get("wins", 0), "losses": s.get("losses", 0), "ties": s.get("ties", 0),
            "pf": round(pf, 2), "pa": round(pa, 2),
            "waiver_priority": s.get("waiver_position"),
            "total_moves": s.get("total_moves", 0),
            "is_andrew": rid == andrew_rid,
        })
    # sort: wins desc, then PF desc -- Sleeper's own tiebreak
    standings.sort(key=lambda x: (-x["wins"], -x["pf"]))
    playoff_teams = (config.get("calendar") or {}).get("playoff_teams") or \
                    ((league or {}).get("settings") or {}).get("playoff_teams") or 6
    for i, row in enumerate(standings, start=1):
        row["rank"] = i
        row["playoff_position"] = "in" if i <= playoff_teams else "out"

    if standings and all(r["wins"] == 0 and r["losses"] == 0 for r in standings):
        warnings.append("every team is 0-0; standings order is PF-only and not meaningful yet")

    waiver_order = [
        {"waiver_priority": r["waiver_priority"], "roster_id": r["roster_id"], "owner": r["owner"]}
        for r in sorted(standings, key=lambda x: (x["waiver_priority"] is None, x["waiver_priority"]))
    ]
    andrew_wp = next((r["waiver_priority"] for r in standings if r["roster_id"] == andrew_rid), None)
    teams_ahead = [w["owner"] for w in waiver_order
                   if w["waiver_priority"] is not None and andrew_wp is not None
                   and w["waiver_priority"] < andrew_wp]

    # ---- per-team detail ----
    teams: Dict[str, Any] = {}
    all_rostered: set = set()
    injuries_all: List[Dict[str, Any]] = []

    for r in rosters:
        rid = r.get("roster_id")
        players = [p for p in (r.get("players") or []) if p]
        all_rostered.update(players)
        starters, bench, notes = split_starters_bench(r, starter_slots, pc)
        starter_ids = [s["player_id"] for s in starters if s.get("player_id")]

        team_injuries = []
        for pid in players:
            rec = pc.get(pid)
            st = rec.get("injury_status")
            if st:
                entry = {
                    "player_id": pid, "player": rec.get("name"), "pos": rec.get("pos"),
                    "team": rec.get("team"), "status": st,
                    "body_part": rec.get("injury_body_part"),
                    "practice": rec.get("practice_participation"),
                    "severity": INJURY_SEVERITY.get(st, 2),
                    "is_starter": pid in starter_ids,
                    "since_week": week,
                    "owner": roster_owner.get(rid),
                    "roster_id": rid,
                }
                team_injuries.append(entry)
                injuries_all.append(entry)
        team_injuries.sort(key=lambda x: (-x["severity"], not x["is_starter"]))

        unresolved = [p for p in players if pc.get(p).get("unresolved")]
        if unresolved:
            notes.append(f"{len(unresolved)} player id(s) not yet in players_cache.json: "
                         + ", ".join(unresolved))

        teams[str(rid)] = {
            "roster_id": rid,
            "owner": roster_owner.get(rid),
            "team_name": ((user_by_id.get(r.get("owner_id")) or {}).get("metadata") or {}).get("team_name"),
            "is_andrew": rid == andrew_rid,
            "players": players,
            "starter_ids": starter_ids,
            "bench_ids": [b["player_id"] for b in bench],
            "starters": starters,
            "bench": bench,
            "positional_counts": positional_counts(players, pc),
            "injuries": team_injuries,
            "bye_weeks": bye_coverage(players, week, byes, starter_ids, pc),
            "locked_keepers": r.get("keepers") or [],
            "waiver_priority": (r.get("settings") or {}).get("waiver_position"),
            "roster_notes": notes,
            "unresolved_player_ids": unresolved,
        }

    injuries_all.sort(key=lambda x: (-x["severity"], x["owner"] or ""))

    # ---- free-agent pool -------------------------------------------------
    # This is the hard gate from plan Part 7: a player is only recommendable if
    # he is provably NOT on a roster in THIS league.
    cached_ids = set(pc.players.keys())
    fa_ids = sorted(cached_ids - all_rostered - set(NFL_TEAMS))
    free_agents = []
    for pid in fa_ids:
        rec = pc.players.get(pid) or {}
        if not rec.get("name"):
            continue
        free_agents.append({"player_id": pid, "name": rec.get("name"),
                            "pos": rec.get("pos"), "team": rec.get("team")})
    free_def = sorted(set(NFL_TEAMS) - all_rostered)

    trending_out = []
    for t in trending or []:
        if isinstance(t, dict) and t.get("player_id"):
            pid = str(t["player_id"])
            trending_out.append({
                "player_id": pid, "player": pc.display(pid),
                "adds_24h": t.get("count"),
                "rostered_in_league": pid in all_rostered,
            })

    # ---- diff vs previous week ------------------------------------------
    prev_path = os.path.join(out_dir, f"week_{week - 1}.json") if isinstance(week, int) else None
    prev_state = _read_json(prev_path) if prev_path else None
    if prev_path and not prev_state:
        warnings.append(f"no previous state at {prev_path}; roster_diff will be empty "
                        "(expected on the first run)")
    diff = roster_diff(prev_state, teams, pc)

    txn_log = normalise_transactions(txn_raw, week, roster_owner, pc)

    # ---- open questions carried from config ------------------------------
    for q in config.get("open_questions", []):
        if q.get("status") == "open":
            open_questions.append(f"[{q.get('id')}] {q.get('question')} "
                                  f"(impact: {q.get('impact')})")
    if not any(t.get("injuries") for t in teams.values()):
        open_questions.append(
            "No injury_status on any cached player. Sleeper's roster endpoint carries none; "
            "injuries come from GET /v1/players/nfl/{id} into players_cache.json. "
            "Run the per-player refresh in fetch_manifest.md step 6 before trusting the injury list."
        )

    # Players whose team/injury data has never come from the authoritative
    # per-player endpoint. Their NFL team may be a season out of date.
    stale_rostered = pc.stale_ids(sorted(all_rostered))
    if stale_rostered:
        open_questions.append(
            f"{len(stale_rostered)} rostered player(s) still carry draft-vintage team/injury data "
            f"and have never been refreshed from GET /v1/players/nfl/{{id}}. Their NFL team may be "
            f"a full season stale (this is how Mike Evans read as TB after signing with SF). "
            f"Run `python3 players_cache.py stale --roster-file raw/rosters.json` for the list, "
            f"then fetch_manifest.md step 7."
        )

    waivers_cfg = config.get("waivers") or {}
    lg_settings = (league or {}).get("settings") or {}
    wt = lg_settings.get("waiver_type", waivers_cfg.get("type_code"))

    state = {
        "meta": {
            "league_id": league_id,
            "previous_league_id": (league or {}).get("previous_league_id"),
            "season": season,
            "week": week,
            "generated_at": _now(),
            "generator": "state_builder.py",
            "season_phase": _season_phase(week, config),
            "league_status": (league or {}).get("status"),
            "nfl_state": {"week": nfl_state.get("week"),
                          "season_type": nfl_state.get("season_type"),
                          "display_week": nfl_state.get("display_week")},
            "waiver": {
                "type_code": wt,
                "type": "FAAB" if wt == 2 else "reverse_standings_rolling_priority" if wt == 1
                        else "rolling_priority" if wt == 0 else "unknown",
                "is_faab": wt == 2,
                "process_day": waivers_cfg.get("waiver_day_name", "Wednesday"),
                "day_of_week_code": lg_settings.get("waiver_day_of_week",
                                                    waivers_cfg.get("waiver_day_of_week")),
                "clear_days": lg_settings.get("waiver_clear_days",
                                              waivers_cfg.get("waiver_clear_days")),
                "submit_deadline_guidance": waivers_cfg.get("run_deadline_guidance"),
            },
            "trade_deadline_week": (config.get("calendar") or {}).get("trade_deadline_week")
                                   or lg_settings.get("trade_deadline"),
            "playoff_week_start": (config.get("calendar") or {}).get("playoff_week_start")
                                   or lg_settings.get("playoff_week_start"),
            "starter_slots": starter_slots,
            "sources": {
                "loaded": ld.loaded,
                "missing": ld.missing,
                "unparseable": ld.broken,
                "players_cache": {
                    "total_ids": len(pc.players),
                    "named": sum(1 for p in pc.players.values() if p.get("name")),
                    "unresolved": sum(1 for p in pc.players.values() if not p.get("name")),
                    # Seeded from a draft payload only, so team/injury are frozen
                    # at that draft's date. Refresh via fetch_manifest step 7.
                    "stale_rostered": len(stale_rostered),
                    "stale_rostered_ids": stale_rostered,
                },
            },
            "warnings": warnings,
            "degraded": bool(ld.missing or ld.broken),
        },

        "standings": standings,
        "waiver_order": waiver_order,
        "andrew_waiver_position": andrew_wp,
        "teams_picking_ahead_of_andrew": teams_ahead,

        "teams": teams,

        "transaction_log": txn_log,
        "roster_diff": diff,
        "matchups": normalise_matchups(matchups, roster_owner, pc),

        "injuries": injuries_all,

        "bye_coverage": {rid: t["bye_weeks"] for rid, t in teams.items()},

        "free_agents": {
            "_gate": "A player may only be recommended if he appears here. Anything not in "
                     "players_cache.json is simply unknown, NOT confirmed available.",
            "confirmed_available_known_players": free_agents,
            "available_defenses": free_def,
            "count": len(free_agents),
            "caveat": "This is the complement of rostered ids against the LOCAL cache only. "
                      "It is a proof of non-availability, not a complete FA pool. To rank the "
                      "real pool, cross-reference trending_add plus the news agents' names and "
                      "check each against the rostered set below.",
            "rostered_player_ids": sorted(all_rostered),
        },

        "trending_adds": trending_out,

        # Populated by later phases of the weekly run; carried forward so the
        # schema is stable and downstream agents can always write into it.
        "opponent_model": (prev_state or {}).get("opponent_model", {}),
        "keeper_equity": (prev_state or {}).get("keeper_equity", []),
        "decisions_log": (prev_state or {}).get("decisions_log", []),

        "open_questions": open_questions,
    }
    return state


# ---------------------------------------------------------------------------
# summary printer
# ---------------------------------------------------------------------------

def print_summary(st: Dict[str, Any]) -> None:
    m = st["meta"]
    print("=" * 74)
    print(f" SUNDAY SCARIES  |  week {m['week']}  |  season {m['season']}  |  "
          f"phase: {m['season_phase']['name']}")
    print("=" * 74)
    print(f" league {m['league_id']}   status={m['league_status']}   generated {m['generated_at']}")
    w = m["waiver"]
    print(f" waivers: {w['type']} (code {w['type_code']}, faab={w['is_faab']}) "
          f"process {w['process_day']}, clear {w['clear_days']}d")
    print(f" trade deadline wk {m['trade_deadline_week']}   playoffs start wk {m['playoff_week_start']}")
    pcs = m["sources"]["players_cache"]
    print(f" players_cache: {pcs['named']} named / {pcs['total_ids']} ids "
          f"({pcs['unresolved']} unresolved)")
    print(f" raw loaded: {', '.join(m['sources']['loaded']) or '(none)'}")
    if m["sources"]["missing"]:
        print(f" raw MISSING: {', '.join(m['sources']['missing'])}")

    print("\n-- STANDINGS " + "-" * 61)
    print(f"  {'#':>2} {'owner':<16} {'rec':>7} {'PF':>8} {'wvr':>4}  seed")
    for r in st["standings"]:
        mark = " <== ANDREW" if r["is_andrew"] else ""
        rec = f"{r['wins']}-{r['losses']}" + (f"-{r['ties']}" if r["ties"] else "")
        print(f"  {r['rank']:>2} {(r['owner'] or '?'):<16} {rec:>7} {r['pf']:>8.2f} "
              f"{str(r['waiver_priority']):>4}  {r['playoff_position']}{mark}")

    print(f"\n-- WAIVER ORDER (priority 1 claims first) " + "-" * 32)
    print("  " + "  ".join(f"{x['waiver_priority']}.{x['owner']}" for x in st["waiver_order"]))
    print(f"  Andrew is #{st['andrew_waiver_position']}; "
          f"{len(st['teams_picking_ahead_of_andrew'])} team(s) claim first: "
          f"{', '.join(st['teams_picking_ahead_of_andrew']) or '(none)'}")

    andrew = next((t for t in st["teams"].values() if t.get("is_andrew")), None)
    if andrew:
        print(f"\n-- ANDREW'S LINEUP (roster {andrew['roster_id']}) " + "-" * 34)
        for s in andrew["starters"]:
            if s.get("empty"):
                print(f"  {s['slot']:<11} -- EMPTY --")
            else:
                flag = "  !! SLOT MISMATCH" if s.get("slot_mismatch") else ""
                inj = f"  [{s['injury_status']}]" if s.get("injury_status") else ""
                print(f"  {s['slot']:<11} {(s['name'] or 'UNKNOWN(' + s['player_id'] + ')'):<24} "
                      f"{(s['pos'] or '?'):<4}{(s['team'] or ''):<4}{inj}{flag}")
        print(f"  {'BENCH':<11} " + ", ".join(
            (b["name"] or f"UNKNOWN({b['player_id']})") + f" ({b['pos'] or '?'})"
            for b in andrew["bench"]) or "(empty)")
        print(f"  counts: {andrew['positional_counts']}")
        for n in andrew["roster_notes"]:
            print(f"  note: {n}")

    print(f"\n-- TRANSACTIONS (week {st['meta']['week']}) " + "-" * 40)
    if not st["transaction_log"]:
        print("  (none loaded)")
    for t in st["transaction_log"][:15]:
        pr = f" prio={t['priority_used']}" if t.get("priority_used") is not None else ""
        a = ", ".join(x["player"] for x in t["added"]) or "-"
        d = ", ".join(x["player"] for x in t["dropped"]) or "-"
        print(f"  [{t['status']:<8} {t['type']:<10}] {', '.join(t['teams']):<16} +{a}  -{d}{pr}")
    if len(st["transaction_log"]) > 15:
        print(f"  ... and {len(st['transaction_log']) - 15} more")

    print("\n-- DIFF vs PREVIOUS WEEK " + "-" * 49)
    d = st["roster_diff"]
    if d["status"] != "ok":
        print(f"  {d['status']}: {d.get('note')}")
    else:
        print(f"  vs week {d['vs_week']}: {d['totals']['added']} adds, {d['totals']['dropped']} drops")
        for rid in d["active_teams"]:
            e = d["by_team"][rid]
            print(f"  {e['owner']:<16} +{[x['player'] for x in e['added']]} "
                  f"-{[x['player'] for x in e['dropped']]}")

    print("\n-- INJURIES " + "-" * 62)
    if not st["injuries"]:
        print("  (none known - see open_questions)")
    for i in st["injuries"][:20]:
        print(f"  {i['status']:<11} {i['player']:<24} {i['pos'] or '?':<4} "
              f"{i['owner']:<16} {'STARTER' if i['is_starter'] else 'bench'}")

    print("\n-- FREE AGENTS (confirmed off every roster) " + "-" * 31)
    fa = st["free_agents"]
    print(f"  {fa['count']} known players + {len(fa['available_defenses'])} DEF")
    for p in fa["confirmed_available_known_players"][:12]:
        print(f"    {p['name']} ({p['pos']}-{p['team']})")
    if fa["count"] > 12:
        print(f"    ... and {fa['count'] - 12} more")

    if st["open_questions"]:
        print("\n-- OPEN QUESTIONS " + "-" * 56)
        for q in st["open_questions"]:
            print(f"  ? {q}")
    if m["warnings"]:
        print("\n-- WARNINGS " + "-" * 62)
        for wn in m["warnings"]:
            print(f"  ! {wn}")
    print()


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Build state/week_N.json from system/raw/*.json")
    ap.add_argument("--week", type=int, default=None,
                    help="week number; inferred from raw/state_nfl.json if omitted")
    ap.add_argument("--raw-dir", default=DEFAULT_RAW)
    ap.add_argument("--out-dir", default=DEFAULT_STATE)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--summary", action="store_true", help="print a human-readable summary")
    ap.add_argument("--dry-run", action="store_true", help="do not write the state file")
    args = ap.parse_args()

    if not os.path.isdir(args.raw_dir):
        print(f"FATAL: raw dir {args.raw_dir} does not exist. "
              f"Run the WebFetch steps in fetch_manifest.md first.", file=sys.stderr)
        return 2

    state = build(args.week, args.raw_dir, args.out_dir, args.config)
    week = state["meta"]["week"]

    if not args.dry_run:
        os.makedirs(args.out_dir, exist_ok=True)
        out = os.path.join(args.out_dir, f"week_{week}.json")
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1)
            fh.write("\n")
        os.replace(tmp, out)
        print(f"wrote {out}  ({os.path.getsize(out):,} bytes)")

    if args.summary:
        print_summary(state)
    elif args.dry_run:
        print(json.dumps(state, indent=1)[:4000])

    if state["meta"]["degraded"]:
        print(f"NOTE: run was degraded - missing {state['meta']['sources']['missing']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
