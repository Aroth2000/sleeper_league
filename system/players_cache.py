#!/usr/bin/env python3
"""
players_cache.py -- incremental player_id -> {name, pos, team} cache for the
Sunday Scaries weekly system.

WHY THIS EXISTS
---------------
Sleeper's full player dump (/v1/players/nfl) is ~5MB and cannot be pulled
through the WebFetch tool intact, and no HTTP client in this sandbox can reach
api.sleeper.app directly. So instead of one big dump we accumulate, week over
week, exactly the subset of players this league actually touches.

SOURCES IT CAN HARVEST FROM (all handled by one ingest call)
  1. Draft-pick payloads       -- richest source; every pick embeds first/last
                                  name, position and team. One 2025 draft seeds
                                  ~160 players in a single shot.
  2. Single-player payloads    -- GET /v1/players/nfl/{player_id} returns a full
                                  player object. VERIFIED WORKING through
                                  WebFetch on 2026-08-07. This is the fallback
                                  for any id the draft never covered, and it is
                                  also where injury_status comes from.
  3. Transaction payloads      -- NOTE: this league's /transactions/{week}
                                  responses carry NO player metadata block
                                  (verified against 2025 week 8). The ingester
                                  still accepts them, but they only contribute
                                  "seen" ids, not names. Those ids land in the
                                  unresolved list so the WebFetch step knows to
                                  go fetch them individually.
  4. Team defences             -- ids like "KC"/"JAX" are synthesised locally.

DESIGN CONTRACT
  * Idempotent. Running it twice over the same input changes nothing.
  * Merge-on-write. Existing entries are never blanked by a payload that has
    less information than what is already cached; richer data wins, and a
    newer explicit value beats an older explicit value.
  * Pure stdlib.
  * Never raises on a malformed payload -- it skips and counts.

CLI
  python3 players_cache.py ingest <file> [<file> ...]
  python3 players_cache.py ingest --dir system/raw
  python3 players_cache.py lookup <player_id> [<player_id> ...]
  python3 players_cache.py unresolved [--roster-file system/raw/rosters.json]
  python3 players_cache.py stale      [--roster-file system/raw/rosters.json]
  python3 players_cache.py stats

Importable:
  from players_cache import PlayersCache
  pc = PlayersCache(); pc.ingest_file(path); pc.save()
"""

from __future__ import annotations

import json
import os
import sys
import glob
import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CACHE = os.path.join(HERE, "players_cache.json")
DEFAULT_RAW_DIR = os.path.join(HERE, "raw")

# ---------------------------------------------------------------------------
# NFL team defences. Sleeper uses the bare team abbreviation as the player_id
# for a DEF, so these can be synthesised without any network call.
# ---------------------------------------------------------------------------
NFL_TEAMS = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

# ---------------------------------------------------------------------------
# Manual corrections.
#
# Raw JSON reaches this sandbox via WebFetch, which passes the response through
# a small language model. That is normally lossless but is not guaranteed to
# be, so any field we later discover was mistranscribed gets pinned here.
# Overrides are applied on every save and always win.
# ---------------------------------------------------------------------------
OVERRIDES: Dict[str, Dict[str, Any]] = {
    # 2025 draft pick #160 came back from WebFetch with position "WR".
    # Hunter Henry is and has always been a TE. Pinning it so lineup logic,
    # which is position-driven, cannot be poisoned by the transcription slip.
    "3214": {"pos": "TE", "_override_reason": "WebFetch transcribed 2025 draft pick 160 as WR; Hunter Henry is a TE"},
}

VALID_POS = {"QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB"}

# Files in system/raw/ that `ingest --dir` must skip.
#   league.json / state_nfl.json  -- contain no player ids at all.
#   transactions_2025_week8.json  -- a kept evidence sample proving this league runs
#       priority waivers, not FAAB (see fetch_manifest.md). Ingesting it would inject
#       ~11 ids for players who have since left the league, and because transaction
#       payloads carry no names those ids would sit in the unresolved queue forever,
#       inviting pointless refetches of players nobody in this league rosters.
INGEST_SKIP = {
    "league.json",
    "state_nfl.json",
    "transactions_2025_week8.json",
}

# Fields whose ABSENCE is itself meaningful, but only when the payload is
# authoritative (i.e. a full object from GET /v1/players/nfl/{id}, which always
# returns the complete key set).
#
# Without this, merge-on-write can only ever add information, so a player who
# gets cut keeps his old team forever and -- much worse -- a player who heals
# keeps "Questionable" for the rest of the season. Both were live bugs:
# Joe Mixon stayed on HOU after going unsigned. Partial payloads (draft picks,
# transactions) are NOT authoritative and still cannot blank anything.
CLEARABLE_ON_AUTHORITATIVE = {
    "team", "injury_status", "injury_body_part", "injury_notes",
    "practice_participation", "depth_chart_position", "depth_chart_order",
    "status",
}

# Any one of these keys marks a record as a full /v1/players/nfl/{id} object
# rather than a draft pick or a transaction row. A draft-pick payload carries
# player identity inside a `metadata` block and never carries these.
# Kept deliberately wide: a single surviving key is enough to route correctly,
# so losing several to a lossy WebFetch transcription is survivable.
PLAYER_OBJECT_KEYS = {
    "fantasy_positions", "search_rank", "birth_date",
    "injury_status", "injury_body_part", "injury_notes",
    "practice_participation", "depth_chart_position", "depth_chart_order",
    "years_exp", "college", "age", "active", "status", "number",
}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


class PlayersCache:
    """Merge-on-write player id cache."""

    def __init__(self, path: str = DEFAULT_CACHE):
        self.path = path
        self.players: Dict[str, Dict[str, Any]] = {}
        self.meta: Dict[str, Any] = {}
        self.stats = {
            "files_read": 0,
            "records_seen": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "id_only": 0,
            "skipped": 0,
            "errors": [],
        }
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except (OSError, ValueError) as exc:
            self.stats["errors"].append(f"could not read existing cache {self.path}: {exc}")
            return
        # tolerate both {"players": {...}} and a bare {id: {...}} map
        if isinstance(blob, dict) and "players" in blob and isinstance(blob["players"], dict):
            self.players = blob["players"]
            self.meta = blob.get("meta", {})
        elif isinstance(blob, dict):
            self.players = {k: v for k, v in blob.items() if isinstance(v, dict)}

    def save(self) -> str:
        self._apply_overrides()
        self.meta.update({
            "updated_at": _now(),
            "count": len(self.players),
            "resolved": sum(1 for p in self.players.values() if p.get("name")),
            "id_only": sum(1 for p in self.players.values() if not p.get("name")),
            "schema": "player_id -> {name, pos, team, first_name, last_name, ...}",
        })
        tmp = self.path + ".tmp"
        payload = {"meta": self.meta, "players": dict(sorted(self.players.items()))}
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, sort_keys=False)
            fh.write("\n")
        os.replace(tmp, self.path)   # atomic; a crashed run cannot truncate the cache
        return self.path

    def _apply_overrides(self) -> None:
        for pid, patch in OVERRIDES.items():
            rec = self.players.setdefault(pid, {"player_id": pid, "sources": ["override"]})
            rec.update(patch)

    # -- core merge ---------------------------------------------------------

    def upsert(self, player_id: Any, fields: Dict[str, Any], source: str = "unknown",
               authoritative: bool = False) -> str:
        """Merge one player. Returns 'created' | 'updated' | 'unchanged' | 'id_only'.

        authoritative=True marks the payload as a complete player object, which
        licenses it to CLEAR the volatile fields in CLEARABLE_ON_AUTHORITATIVE
        (team, injury_status, ...). Everything else is still merge-only.
        """
        pid = _clean(player_id)
        if not pid or pid == "0":       # Sleeper uses "0" as an empty starter slot
            self.stats["skipped"] += 1
            return "skipped"

        incoming = {k: v for k, v in fields.items() if v not in (None, "", [], {})}

        # Explicit nulls from an authoritative payload are real information.
        cleared = {}
        if authoritative:
            for k in CLEARABLE_ON_AUTHORITATIVE:
                if k in fields and fields[k] in (None, ""):
                    cleared[k] = None

        # normalise position
        pos = _clean(incoming.get("pos") or incoming.get("position"))
        if pos:
            pos = pos.upper()
            if pos not in VALID_POS:
                fp = incoming.get("fantasy_positions")
                if isinstance(fp, list) and fp:
                    pos = str(fp[0]).upper()
            incoming["pos"] = pos
        incoming.pop("position", None)

        # build a display name if we only got the parts
        first = _clean(incoming.get("first_name"))
        last = _clean(incoming.get("last_name"))
        if not incoming.get("name") and (first or last):
            incoming["name"] = " ".join(x for x in (first, last) if x)

        team = _clean(incoming.get("team"))
        if team:
            incoming["team"] = team.upper()

        # a DEF's "name" is the club; keep team and pos consistent
        if pid in NFL_TEAMS and not incoming.get("name"):
            incoming.setdefault("name", NFL_TEAMS[pid])
            incoming.setdefault("pos", "DEF")
            incoming.setdefault("team", pid)

        keep = (
            "name", "first_name", "last_name", "pos", "team", "number",
            "age", "years_exp", "college", "status", "injury_status",
            "injury_body_part", "injury_notes", "practice_participation",
            "depth_chart_position", "depth_chart_order", "search_rank",
            "fantasy_positions", "active", "news_updated",
        )
        incoming = {k: v for k, v in incoming.items() if k in keep}
        # Apply authorised clears last so they win over nothing but themselves.
        incoming.update({k: v for k, v in cleared.items() if k in keep})

        existing = self.players.get(pid)
        if existing is None:
            rec = {"player_id": pid}
            rec.update(incoming)
            rec["sources"] = [source]
            rec["first_seen"] = _now()
            rec["last_updated"] = _now()
            self.players[pid] = rec
            if rec.get("name"):
                self.stats["created"] += 1
                return "created"
            self.stats["id_only"] += 1
            return "id_only"

        changed = False
        for k, v in incoming.items():
            if existing.get(k) != v:
                existing[k] = v
                changed = True
        srcs = existing.setdefault("sources", [])
        if source not in srcs:
            srcs.append(source)
        if changed:
            existing["last_updated"] = _now()
            self.stats["updated"] += 1
            return "updated"
        self.stats["unchanged"] += 1
        return "unchanged"

    def note_id(self, player_id: Any, source: str = "seen") -> None:
        """Record that an id exists without claiming to know anything about it."""
        pid = _clean(player_id)
        if not pid or pid == "0":
            return
        if pid in NFL_TEAMS:
            self.upsert(pid, {}, source=source)
            return
        if pid not in self.players:
            self.players[pid] = {
                "player_id": pid,
                "sources": [source],
                "first_seen": _now(),
                "last_updated": _now(),
            }
            self.stats["id_only"] += 1
        else:
            srcs = self.players[pid].setdefault("sources", [])
            if source not in srcs:
                srcs.append(source)

    # -- payload shape handlers --------------------------------------------

    def ingest_draft_pick(self, pick: Dict[str, Any], source: str = "draft") -> None:
        """Handles both the native Sleeper shape (metadata block) and the
        flattened per-pick shape the WebFetch step emits."""
        md = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
        fields = {
            "first_name": pick.get("first_name") or md.get("first_name"),
            "last_name": pick.get("last_name") or md.get("last_name"),
            "pos": pick.get("position") or md.get("position"),
            "team": pick.get("team") or md.get("team"),
            "number": md.get("number"),
            "status": md.get("status"),
            "injury_status": md.get("injury_status"),
        }
        self.upsert(pick.get("player_id") or md.get("player_id"), fields, source=source)

    def ingest_transaction(self, txn: Dict[str, Any], source: str = "transaction") -> None:
        """Transactions in this league carry no player metadata (verified), so
        this mostly records ids. If Sleeper ever starts embedding metadata the
        block below picks it up for free."""
        md = txn.get("metadata")
        for bucket in ("adds", "drops"):
            grp = txn.get(bucket)
            if isinstance(grp, dict):
                for pid in grp:
                    self.note_id(pid, source=source)
        if isinstance(md, dict) and md.get("player_id"):
            self.ingest_draft_pick(md, source=source)
        # some Sleeper responses attach a players[] array of full objects
        for p in txn.get("players", []) or []:
            if isinstance(p, dict):
                self.ingest_player_object(p, source=source)

    def ingest_player_object(self, obj: Dict[str, Any], source: str = "player_endpoint") -> None:
        """A full object from GET /v1/players/nfl/{id}."""
        self.upsert(obj.get("player_id"), {
            "first_name": obj.get("first_name"),
            "last_name": obj.get("last_name"),
            "pos": obj.get("position"),
            "team": obj.get("team"),
            "number": obj.get("number"),
            "age": obj.get("age"),
            "years_exp": obj.get("years_exp"),
            "college": obj.get("college"),
            "status": obj.get("status"),
            "injury_status": obj.get("injury_status"),
            "injury_body_part": obj.get("injury_body_part"),
            "injury_notes": obj.get("injury_notes"),
            "practice_participation": obj.get("practice_participation"),
            "depth_chart_position": obj.get("depth_chart_position"),
            "depth_chart_order": obj.get("depth_chart_order"),
            "search_rank": obj.get("search_rank"),
            "fantasy_positions": obj.get("fantasy_positions"),
            "active": obj.get("active"),
            "news_updated": obj.get("news_updated"),
        }, source=source, authoritative=True)

    def ingest_roster(self, roster: Dict[str, Any], source: str = "roster") -> None:
        for key in ("players", "starters", "reserve", "taxi", "keepers"):
            for pid in roster.get(key) or []:
                self.note_id(pid, source=source)

    def seed_defenses(self) -> None:
        for abbr in NFL_TEAMS:
            self.upsert(abbr, {}, source="builtin_def")

    # -- dispatch -----------------------------------------------------------

    def ingest_records(self, records: Iterable[Any], source: str) -> None:
        for rec in records:
            if not isinstance(rec, dict):
                self.stats["skipped"] += 1
                continue
            self.stats["records_seen"] += 1
            try:
                if "pick_no" in rec or "draft_slot" in rec or "draft_id" in rec:
                    self.ingest_draft_pick(rec, source=source)
                elif "transaction_id" in rec or "adds" in rec or "drops" in rec:
                    self.ingest_transaction(rec, source=source)
                elif "roster_id" in rec and ("players" in rec or "starters" in rec):
                    self.ingest_roster(rec, source=source)
                elif "player_id" in rec:
                    # Full player object, or any flattened row carrying a name.
                    # The discriminator must be WIDE. WebFetch transcribes JSON
                    # through a small model and is not guaranteed lossless, and the
                    # keys it is most likely to drop are exactly the decorative ones
                    # (fantasy_positions, search_rank, birth_date). If a
                    # /players/nfl/{id} response is misrouted to ingest_draft_pick it
                    # is treated as NON-authoritative and injury_status/team are
                    # silently discarded -- the player reads as healthy, vacancy
                    # pressure reads as zero, and nothing anywhere reports an error.
                    if PLAYER_OBJECT_KEYS & set(rec):
                        self.ingest_player_object(rec, source=source)
                    else:
                        self.ingest_draft_pick(rec, source=source)
                else:
                    self.stats["skipped"] += 1
            except Exception as exc:                      # never die on one bad row
                self.stats["errors"].append(f"{source}: {exc}")
                self.stats["skipped"] += 1

    @staticmethod
    def _read_any(path: str) -> List[Any]:
        """Reads .json (object or array) or .jsonl. Returns a list of records."""
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            return []
        if path.endswith(".jsonl") or (text[0] == "{" and "\n{" in text):
            out = []
            for line in text.splitlines():
                line = line.strip().rstrip(",")
                if not line or line in ("[", "]"):
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
            if out:
                return out
        blob = json.loads(text)
        if isinstance(blob, list):
            return blob
        if isinstance(blob, dict):
            for key in ("players", "picks", "transactions", "rosters", "data"):
                if isinstance(blob.get(key), list):
                    return blob[key]
            return [blob]
        return []

    def ingest_file(self, path: str) -> int:
        try:
            records = self._read_any(path)
        except (OSError, ValueError) as exc:
            self.stats["errors"].append(f"{os.path.basename(path)}: {exc}")
            return 0
        source = os.path.splitext(os.path.basename(path))[0]
        before = len(self.players)
        self.ingest_records(records, source=source)
        self.stats["files_read"] += 1
        return len(self.players) - before

    def ingest_dir(self, directory: str) -> None:
        files = sorted(glob.glob(os.path.join(directory, "*.json"))
                       + glob.glob(os.path.join(directory, "*.jsonl")))
        for f in files:
            if os.path.basename(f) in INGEST_SKIP:
                continue
            self.ingest_file(f)

    # -- queries ------------------------------------------------------------

    def get(self, player_id: Any) -> Dict[str, Any]:
        pid = _clean(player_id) or ""
        rec = self.players.get(pid)
        if rec and rec.get("name"):
            return rec
        return {"player_id": pid, "name": None, "pos": None, "team": None, "unresolved": True}

    def display(self, player_id: Any) -> str:
        rec = self.get(player_id)
        if not rec.get("name"):
            return f"UNKNOWN({player_id})"
        bits = rec["name"]
        tags = [t for t in (rec.get("pos"), rec.get("team")) if t]
        return f"{bits} ({'-'.join(tags)})" if tags else bits

    def stale_ids(self, restrict_to: Optional[Iterable[str]] = None,
                  authoritative_source: str = "players_resolved") -> List[str]:
        """Ids whose data has never come from the authoritative player endpoint.

        These were seeded from a draft-pick payload, so their team/injury fields
        are frozen at that draft's date. Real example: the 2025 draft had Mike
        Evans on TB and Kenneth Walker on SEA; both had moved by 2026. Anything
        listed here needs a GET /v1/players/nfl/{id} refresh before its team or
        injury status can be trusted.
        """
        pool = list(restrict_to) if restrict_to is not None else list(self.players)
        out = []
        for pid in pool:
            pid = _clean(pid) or ""
            rec = self.players.get(pid)
            if not rec or rec.get("pos") == "DEF" or pid in NFL_TEAMS:
                continue
            if authoritative_source not in (rec.get("sources") or []):
                out.append(pid)
        return sorted(set(out))

    def unresolved_ids(self, restrict_to: Optional[Iterable[str]] = None) -> List[str]:
        pool = list(restrict_to) if restrict_to is not None else list(self.players)
        out = []
        for pid in pool:
            pid = _clean(pid) or ""
            if not pid or pid == "0":
                continue
            rec = self.players.get(pid)
            if not rec or not rec.get("name"):
                out.append(pid)
        return sorted(set(out))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_ingest(argv: List[str]) -> int:
    pc = PlayersCache()
    pc.seed_defenses()
    if "--dir" in argv:
        i = argv.index("--dir")
        d = argv[i + 1] if len(argv) > i + 1 else DEFAULT_RAW_DIR
        pc.ingest_dir(d)
    else:
        paths = [a for a in argv if not a.startswith("--")]
        if not paths:
            pc.ingest_dir(DEFAULT_RAW_DIR)
        for p in paths:
            pc.ingest_file(p)
    path = pc.save()
    s = pc.stats
    print(f"players_cache -> {path}")
    print(f"  files read      {s['files_read']}")
    print(f"  records seen    {s['records_seen']}")
    print(f"  created         {s['created']}")
    print(f"  updated         {s['updated']}")
    print(f"  unchanged       {s['unchanged']}")
    print(f"  id-only (no nm) {s['id_only']}")
    print(f"  skipped         {s['skipped']}")
    print(f"  TOTAL cached    {len(pc.players)}  ({pc.meta['resolved']} named, {pc.meta['id_only']} unresolved)")
    for e in s["errors"][:10]:
        print(f"  ! {e}")
    return 0


def _cmd_lookup(argv: List[str]) -> int:
    pc = PlayersCache()
    for pid in argv:
        print(f"{pid:>8}  {pc.display(pid)}")
    return 0


def _cmd_unresolved(argv: List[str]) -> int:
    pc = PlayersCache()
    restrict = None
    if "--roster-file" in argv:
        i = argv.index("--roster-file")
        rf = argv[i + 1]
        try:
            with open(rf, "r", encoding="utf-8") as fh:
                rosters = json.load(fh)
            restrict = []
            for r in rosters:
                restrict.extend(r.get("players") or [])
        except (OSError, ValueError) as exc:
            print(f"could not read {rf}: {exc}", file=sys.stderr)
            return 1
    ids = pc.unresolved_ids(restrict)
    if not ids:
        print("(none - every id is resolved)")
        return 0
    print(f"{len(ids)} unresolved player id(s):")
    for pid in ids:
        print(f"  {pid}   https://api.sleeper.app/v1/players/nfl/{pid}")
    return 0


def _roster_ids(argv: List[str]) -> Optional[List[str]]:
    """--roster-file <path> -> the flat list of every rostered player id."""
    if "--roster-file" not in argv:
        return None
    rf = argv[argv.index("--roster-file") + 1]
    with open(rf, "r", encoding="utf-8") as fh:
        rosters = json.load(fh)
    ids: List[str] = []
    for r in rosters:
        ids.extend(r.get("players") or [])
    return ids


def _cmd_stale(argv: List[str]) -> int:
    pc = PlayersCache()
    try:
        restrict = _roster_ids(argv)
    except (OSError, ValueError, IndexError) as exc:
        print(f"could not read roster file: {exc}", file=sys.stderr)
        return 1
    ids = pc.stale_ids(restrict)
    if not ids:
        print("(none - every player has authoritative data)")
        return 0
    print(f"{len(ids)} player(s) never refreshed from /v1/players/nfl/{{id}} "
          f"(team + injury data may be stale):")
    for pid in ids:
        rec = pc.players.get(pid, {})
        print(f"  {pid:>6}  {(rec.get('name') or '?'):<26} "
              f"{(rec.get('pos') or '?'):<4} {(rec.get('team') or 'FA'):<4}  "
              f"https://api.sleeper.app/v1/players/nfl/{pid}")
    return 0


def _cmd_stats(_argv: List[str]) -> int:
    pc = PlayersCache()
    named = sum(1 for p in pc.players.values() if p.get("name"))
    by_pos: Dict[str, int] = {}
    for p in pc.players.values():
        by_pos[p.get("pos") or "?"] = by_pos.get(p.get("pos") or "?", 0) + 1
    print(f"cache: {pc.path}")
    print(f"total ids: {len(pc.players)}   named: {named}   unresolved: {len(pc.players) - named}")
    for pos, n in sorted(by_pos.items(), key=lambda kv: -kv[1]):
        print(f"  {pos:>4} {n}")
    return 0


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]
    return {
        "ingest": _cmd_ingest,
        "lookup": _cmd_lookup,
        "unresolved": _cmd_unresolved,
        "stale": _cmd_stale,
        "stats": _cmd_stats,
    }.get(cmd, lambda _a: (print(f"unknown command: {cmd}"), 1)[1])(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
