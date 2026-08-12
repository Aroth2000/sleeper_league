#!/usr/bin/env python3
"""
build_dashboard.py -- regenerate system/ui/dashboard.html from real league data.

WHAT THIS IS
------------
The dashboard is the single front end for the Sunday Scaries system. It is ONE
self-contained HTML file: all CSS and JS inline, zero network requests, zero
localStorage/sessionStorage (unsupported in the target viewer and would break
it). Every number in it is baked into a single JSON blob at build time, so the
page is a frozen snapshot with an explicit "data as of" stamp rather than a
live client.

INPUTS (all optional except the state file -- missing inputs degrade to a
clearly-marked NO DATA panel, never to invented content)

  system/state/week_N.json      deterministic ground truth from state_builder.py
                                (rosters, starters, standings, injuries,
                                free agents, warnings). Highest N wins unless
                                --week is given.
  system/league_config.json     league constants, Andrew's keeper plan, pick map
  draft_board_2026.md           the draft research doc; its tier / pick-target /
                                dead-zone / rules tables are parsed out and
                                surfaced on the DRAFT tab. If absent, the DRAFT
                                tab still renders the pick map and keepers from
                                league_config and shows an explicit placeholder
                                where the board would go.
  system/reports/week_N.md      the weekly narrative report, if one exists
  system/analysis/*.py          keeper_equity (2027 board) and opponent_pressure
                                (per-rival pressure) are imported if importable

WHAT IT REFUSES TO DO
---------------------
Nothing on this page is filler. If a section has no real data -- no opponent
model because the synthesis agent has not run, no waiver claim sheet because it
is still preseason -- the section renders a NO DATA panel that names the
producer that would fill it and the condition under which it will. A dashboard
that invents a waiver claim sheet is worse than one that admits it has none.

USAGE
    python3 build_dashboard.py                 # latest week, writes dashboard.html
    python3 build_dashboard.py --week 7
    python3 build_dashboard.py --out /tmp/x.html
    python3 build_dashboard.py --print-data    # dump the JSON payload, no HTML
"""

import argparse
import datetime
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = os.path.dirname(HERE)
ROOT = os.path.dirname(SYSTEM)
STATE_DIR = os.path.join(SYSTEM, "state")
REPORTS_DIR = os.path.join(SYSTEM, "reports")
ANALYSIS_DIR = os.path.join(SYSTEM, "analysis")
CONFIG_PATH = os.path.join(SYSTEM, "league_config.json")
DRAFT_BOARD_PATH = os.path.join(ROOT, "draft_board_2026.md")
DEFAULT_OUT = os.path.join(HERE, "dashboard.html")

POSITION_ORDER = ["QB", "RB", "WR", "TE", "DEF"]


# ---------------------------------------------------------------------------
# small utilities
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return None


def as_dict(obj, label, warnings):
    """These files are partly model-written, so a valid-JSON-but-wrong-type
    payload (a bare list, a string) is a realistic failure. Refuse it loudly
    instead of throwing AttributeError three frames later."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    warnings.append("%s parsed as %s, not a JSON object -- ignoring it."
                    % (label, type(obj).__name__))
    return None


def as_list(obj):
    """Same idea for the array-shaped sections."""
    return obj if isinstance(obj, list) else []


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (IOError, OSError):
        return None


def find_synthesis(week, explicit=None):
    """The synthesis agent's output.

    IMPORTANT SEAM: merge_state.py only folds four MODEL_SECTIONS
    (opponent_model, keeper_equity, decisions_log, open_questions) into
    week_N.json. The action card, lineup card, waiver claim sheet, drop
    candidates and trade board are NOT among them -- weekly.js emits them as
    top-level fields of the synthesis agent's own object, and the documented
    order of operations only ever writes that agent's `state_json` string to
    week_N.synthesis.json. So if you want those on the dashboard, dump the WHOLE
    synthesis object to week_N.synthesis.json (or pass --synthesis PATH). This
    function accepts either shape and simply finds nothing in the state-only one.
    """
    if explicit:
        return explicit, read_json(explicit)
    if week is None:
        return None, None
    p = os.path.join(STATE_DIR, "week_%s.synthesis.json" % week)
    return (p, read_json(p)) if os.path.exists(p) else (None, None)


def find_state(week=None):
    """Locate the state file. Explicit --week wins; otherwise highest week_N."""
    if week is not None:
        p = os.path.join(STATE_DIR, "week_%s.json" % week)
        return p if os.path.exists(p) else None
    if not os.path.isdir(STATE_DIR):
        return None
    best = None
    for name in os.listdir(STATE_DIR):
        m = re.match(r"^week_(-?\d+)\.json$", name)
        if not m:
            continue
        n = int(m.group(1))
        if best is None or n > best[0]:
            best = (n, os.path.join(STATE_DIR, name))
    return best[1] if best else None


# ---------------------------------------------------------------------------
# markdown parsing -- just enough to lift tables and lists out of the board doc
# ---------------------------------------------------------------------------

HEADING_RX = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def md_section(text, pattern, occurrence=1):
    """Body of the first heading whose title matches `pattern`, up to the next
    heading of the same or shallower level."""
    if not text:
        return ""
    rx = re.compile(pattern, re.I)
    lines = text.split("\n")
    hits = 0
    for i, ln in enumerate(lines):
        m = HEADING_RX.match(ln)
        if not (m and rx.search(m.group(2))):
            continue
        hits += 1
        if hits < occurrence:
            continue
        level = len(m.group(1))
        out = []
        for ln2 in lines[i + 1:]:
            m2 = HEADING_RX.match(ln2)
            if m2 and len(m2.group(1)) <= level:
                break
            out.append(ln2)
        return "\n".join(out).strip()
    return ""


def md_subsections(block, level=3):
    """[(title, body)] for every heading of exactly `level` inside a block."""
    out = []
    lines = (block or "").split("\n")
    cur = None
    for ln in lines:
        m = HEADING_RX.match(ln)
        if m and len(m.group(1)) == level:
            if cur:
                out.append((cur[0], "\n".join(cur[1]).strip()))
            cur = (m.group(2), [])
        elif m and len(m.group(1)) < level:
            if cur:
                out.append((cur[0], "\n".join(cur[1]).strip()))
            cur = None
        elif cur is not None:
            cur[1].append(ln)
    if cur:
        out.append((cur[0], "\n".join(cur[1]).strip()))
    return out


def md_tables(block):
    """Every pipe table in a block -> [{'headers': [...], 'rows': [[...]]}]."""
    tables = []
    cur = None
    for raw in (block or "").split("\n"):
        ln = raw.strip()
        is_row = ln.startswith("|") and ln.count("|") >= 2
        if not is_row:
            if cur and cur["rows"]:
                tables.append(cur)
            cur = None
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if cur is None:
            cur = {"headers": cells, "rows": []}
            continue
        if all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
            continue  # the ---|--- separator
        cur["rows"].append(cells)
    if cur and cur["rows"]:
        tables.append(cur)
    return tables


def md_first_table(block):
    t = md_tables(block)
    return t[0] if t else None


def md_list(block, ordered=None):
    """Top-level list items, continuation lines folded in."""
    items = []
    for raw in (block or "").split("\n"):
        ln = raw.rstrip()
        m = re.match(r"^\s{0,3}(?:[-*+]|\d+\.)\s+(.*)$", ln)
        if m:
            items.append(m.group(1).strip())
        elif items and ln.strip() and ln.startswith((" ", "\t")):
            items[-1] += " " + ln.strip()
    return items


def md_blockquote(block):
    out = []
    for raw in (block or "").split("\n"):
        ln = raw.strip()
        if ln.startswith(">"):
            txt = ln.lstrip(">").strip()
            if txt:
                out.append(txt)
    return out


def md_paragraphs(block):
    paras, cur = [], []
    for raw in (block or "").split("\n"):
        ln = raw.strip()
        if not ln:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        if ln.startswith(("|", "#", ">")) or re.match(r"^\s*(?:[-*+]|\d+\.)\s", ln):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(ln)
    if cur:
        paras.append(" ".join(cur))
    return paras


# ---------------------------------------------------------------------------
# DRAFT tab
# ---------------------------------------------------------------------------

def build_draft(cfg, state, warnings):
    andrew = (cfg or {}).get("andrew") or {}
    league = (cfg or {}).get("league") or {}
    roster = (cfg or {}).get("roster") or {}
    rules = (cfg or {}).get("keeper_rules") or {}

    pick_map = ((andrew.get("pick_map_2026") or {}).get("picks")) or []
    if not pick_map:
        warnings.append(
            "league_config.andrew.pick_map_2026 is missing; the DRAFT pick map "
            "could not be built from config.")

    picks = []
    for p in pick_map:
        picks.append({
            "round": p.get("round"),
            "overall": p.get("overall"),
            "status": p.get("status"),
            "reason": p.get("reason"),
        })
    picks.sort(key=lambda x: (x.get("round") or 0))

    live = [p for p in picks if p.get("status") == "live"]
    forfeited = [p for p in picks if p.get("status") != "live"]

    # Dead zones derived from the live pick sequence -- not copied from prose.
    # `nominal` is the count of picks that happen BETWEEN two of Andrew's picks
    # (exclusive), which is the convention the draft board uses: 28 -> 48 is a
    # 19-pick gap, not 20.
    gaps = []
    for a, b in zip(live, live[1:]):
        gaps.append({
            "from": a["overall"], "to": b["overall"],
            "nominal": b["overall"] - a["overall"] - 1,
        })
    for g in gaps:
        g["dead_zone"] = g["nominal"] >= 19

    # Keepers, from the config plan (Sleeper's keepers field is still null).
    keepers = []
    for k in (andrew.get("keeper_plan") or {}).get("keeping") or []:
        max_years = rules.get("max_consecutive_years") or 3
        used = k.get("consecutive_years_if_kept")
        keepers.append({
            "name": k.get("name"),
            "player_id": k.get("player_id"),
            "pos": k.get("pos"),
            "cost_round": k.get("cost_round"),
            "forfeits_overall_pick": k.get("forfeits_overall_pick"),
            "consecutive_years_if_kept": used,
            "years_remaining_after": (max_years - used) if isinstance(used, int) else None,
            "final_eligible_year_if_kept": k.get("final_eligible_year_if_kept"),
        })
    keeper_status = (andrew.get("keeper_plan") or {}).get("status")
    passed_over = (andrew.get("keeper_plan") or {}).get("passed_over") or []

    # Unfilled starting slots after keepers -- computed, not typed in.
    starter_slots = list(roster.get("starter_slots") or [])
    flex_elig = roster.get("flex_eligible") or {}
    remaining = list(starter_slots)
    filled = []
    for k in keepers:
        pos = k.get("pos")
        target = None
        if pos in remaining:
            target = pos
        else:
            for slot in remaining:
                if pos in (flex_elig.get(slot) or []):
                    target = slot
                    break
        if target:
            remaining.remove(target)
            filled.append({"slot": target, "player": k.get("name"), "pos": pos})
    bench_slots = roster.get("num_bench") or 0
    needs = {
        "filled_by_keepers": filled,
        "unfilled_starters": remaining,
        "bench_slots": bench_slots,
        "picks_available": len(live),
        "spots_to_fill": len(remaining) + bench_slots,
    }
    if needs["picks_available"] != needs["spots_to_fill"]:
        warnings.append(
            "DRAFT: %d live picks but %d roster spots to fill -- pick map and "
            "roster settings disagree." % (needs["picks_available"],
                                           needs["spots_to_fill"]))

    draft_dt = league.get("draft_datetime_et")
    countdown = None
    if draft_dt:
        try:
            d = datetime.datetime.fromisoformat(draft_dt)
            now = datetime.datetime.now(datetime.timezone.utc).astimezone(d.tzinfo)
            countdown = round((d - now).total_seconds() / 86400.0, 1)
        except ValueError:
            pass

    out = {
        "slot": andrew.get("draft_slot") or league.get("andrew_draft_slot"),
        "num_teams": league.get("num_teams"),
        "rounds": league.get("draft_rounds"),
        "draft_datetime_et": draft_dt,
        "days_until": countdown,
        "picks": picks,
        "live_overalls": [p["overall"] for p in live],
        "forfeited": forfeited,
        "gaps": gaps,
        "keepers": keepers,
        "keeper_status": keeper_status,
        "passed_over": passed_over,
        "needs": needs,
        "board": build_draft_board(warnings),
    }
    return out


def build_draft_board(warnings):
    """Lift the useful tables out of draft_board_2026.md. If the file is not
    there, return a placeholder the UI renders as an explicit gap."""
    text = read_text(DRAFT_BOARD_PATH)
    if not text:
        warnings.append(
            "draft_board_2026.md not found at %s -- DRAFT tab tier tables are a "
            "placeholder." % DRAFT_BOARD_PATH)
        return {
            "available": False,
            "path": DRAFT_BOARD_PATH,
            "note": ("draft_board_2026.md does not exist yet. Generate it, then "
                     "re-run build_dashboard.py and the tier tables, pick-by-pick "
                     "targets, dead-zone checklist and panic buttons will appear "
                     "here automatically."),
        }

    board = {"available": True, "path": DRAFT_BOARD_PATH, "bytes": len(text)}

    board["tiers"] = md_first_table(md_section(text, r"MASTER VALUE TIER TABLE"))
    board["pick_targets"] = md_first_table(
        md_section(text, r"PICK-BY-PICK TARGET TABLE"))
    board["depletion"] = md_first_table(
        md_section(text, r"ROUND-BY-ROUND KEEPER DEPLETION MAP"))
    board["real_waits"] = md_first_table(
        md_section(text, r"REAL waits, measured in live picks"))
    board["seat_map"] = md_first_table(md_section(text, r"THE SEAT MAP"))
    board["true_pick_map"] = md_first_table(
        md_section(text, r"true pick map"))
    board["checklist"] = md_first_table(
        md_section(text, r"Consolidated pre-dead-zone checklist"))
    board["pivot_triggers"] = md_first_table(
        md_section(text, r"if two of three are gone"))

    dz_block = md_section(text, r"DEAD-ZONE PLANNING")
    board["dead_zone_notes"] = [
        {"title": t, "body": md_paragraphs(b) + md_list(b)}
        for t, b in md_subsections(dz_block, 3)
        if re.match(r"^dead zone", t, re.I)
    ]

    board["one_paragraph"] = " ".join(
        md_paragraphs(md_section(text, r"THE ONE-PARAGRAPH PLAN")))
    board["thirty_second"] = md_blockquote(
        md_section(text, r"THE 30-SECOND VERSION"))

    part_c = md_section(text, r"^PART C")
    rules = []
    for label, pat in (("Inviolable", r"five inviolable rules"),
                       ("Format", r"Format rules"),
                       ("Timing", r"Timing rules")):
        for item in md_list(md_section(part_c, pat)):
            rules.append({"group": label, "text": item})
    board["rules"] = rules

    part_d = md_section(text, r"^PART D")
    board["panics"] = [
        {"title": t, "body": md_paragraphs(b)}
        for t, b in md_subsections(part_d, 3)
    ]

    qb_block = md_section(text, r"THE QB QUESTION")
    qb_head = [t for t, _ in md_subsections(qb_block, 3)]
    board["qb_headline"] = qb_head[0] if qb_head else None
    board["qb_answer"] = ([p for p in md_paragraphs(qb_block) if len(p) > 60]
                          + md_list(qb_block))[:8]

    scenarios = []
    for t, b in md_subsections(md_section(text, r"^PART A"), 2):
        if not t.upper().startswith("SCENARIO"):
            continue
        picks = []
        for sub_t, _ in md_subsections(b, 3):
            m = re.match(r".*?PICK\s+(\d+)\s+[-—]+\s+(.*)$", sub_t)
            if m:
                picks.append({"pick": int(m.group(1)), "take": m.group(2)})
        scenarios.append({"name": t, "picks": picks})
    board["scenarios"] = scenarios

    empties = [k for k in ("tiers", "pick_targets", "checklist")
               if not board.get(k)]
    if empties:
        warnings.append(
            "draft_board_2026.md parsed but these sections were not found: %s"
            % ", ".join(empties))
    return board


# ---------------------------------------------------------------------------
# MY TEAM tab
# ---------------------------------------------------------------------------

def build_my_team(cfg, state, synth, warnings):
    andrew_rid = str(((cfg or {}).get("andrew") or {}).get("roster_id") or 2)
    teams = (state or {}).get("teams")
    teams = teams if isinstance(teams, dict) else {}
    team = teams.get(andrew_rid)
    team = team if isinstance(team, dict) else None
    if not team:
        warnings.append("MY TEAM: roster_id %s not present in the state file."
                        % andrew_rid)
        return {"available": False,
                "note": "No roster for roster_id %s in the state file." % andrew_rid}

    plan = ((cfg or {}).get("andrew") or {}).get("keeper_plan") or {}
    keeping = {k.get("player_id"): k for k in (plan.get("keeping") or [])}
    board = {r.get("player_id"): r for r in
             (((cfg or {}).get("andrew") or {}).get("keeper_cost_board_2026") or [])}
    max_years = ((cfg or {}).get("keeper_rules") or {}).get("max_consecutive_years") or 3

    def decorate(p):
        pid = p.get("player_id")
        k = keeping.get(pid)
        b = board.get(pid) or {}
        row = dict(p)
        row["keeper"] = bool(k)
        row["keeper_cost_round"] = (k or b).get("cost_round")
        row["keeper_eligible"] = b.get("eligible", True) if b else None
        row["keeper_flag"] = b.get("flag")
        if k:
            used = k.get("consecutive_years_if_kept")
            row["consecutive_years_if_kept"] = used
            row["years_remaining_after"] = (max_years - used) if isinstance(used, int) else None
            row["final_eligible_year_if_kept"] = k.get("final_eligible_year_if_kept")
            row["forfeits_overall_pick"] = k.get("forfeits_overall_pick")
        return row

    starters = [decorate(p) for p in (team.get("starters") or [])]
    bench = [decorate(p) for p in (team.get("bench") or [])]

    league_status = ((state or {}).get("meta") or {}).get("league_status")
    lineup_note = None
    if league_status == "pre_draft":
        lineup_note = ("This is the roster Sleeper is carrying into the draft "
                       "(last season's team). The slot assignments are Sleeper's "
                       "leftovers, not a 2026 lineup -- after Aug 28 only the "
                       "three keepers below survive.")

    return {
        "available": True,
        "roster_id": team.get("roster_id"),
        "owner": team.get("owner"),
        "team_name": team.get("team_name"),
        "starters": starters,
        "bench": bench,
        "positional_counts": team.get("positional_counts") or {},
        "injuries": team.get("injuries") or [],
        "bye_weeks": team.get("bye_weeks") or {},
        "waiver_priority": team.get("waiver_priority"),
        "starter_slots": ((state or {}).get("meta") or {}).get("starter_slots") or [],
        "lineup_note": lineup_note,
        "lineup_card": [x for x in as_list((synth or {}).get("lineup_card"))
                        if isinstance(x, dict)],
        "keeper_status": plan.get("status"),
        "roster_notes": team.get("roster_notes") or [],
        "unresolved_player_ids": team.get("unresolved_player_ids") or [],
    }


# ---------------------------------------------------------------------------
# OPPONENTS tab
# ---------------------------------------------------------------------------

def load_pressure(state, warnings):
    """Run analysis/opponent_pressure.py in-process. Returns {} on any failure --
    the UI then shows the section as unavailable rather than blank."""
    if not state:
        return {}
    if ANALYSIS_DIR not in sys.path:
        sys.path.insert(0, ANALYSIS_DIR)
    try:
        import opponent_pressure  # noqa
    except Exception as exc:  # pragma: no cover - import guard
        warnings.append("OPPONENTS: could not import opponent_pressure.py (%s)" % exc)
        return {}
    try:
        return opponent_pressure.compute_league_pressure(state) or {}
    except Exception as exc:
        warnings.append("OPPONENTS: opponent_pressure raised %s: %s"
                        % (type(exc).__name__, exc))
        return {}


def build_opponents(cfg, state, synth, warnings):
    andrew_rid = ((cfg or {}).get("andrew") or {}).get("roster_id") or 2
    teams = (state or {}).get("teams")
    teams = teams if isinstance(teams, dict) else {}
    standings = {s.get("roster_id"): s
                 for s in as_list((state or {}).get("standings"))
                 if isinstance(s, dict)}
    model = (state or {}).get("opponent_model")
    model = model if isinstance(model, dict) else {}
    pressure = load_pressure(state, warnings)
    intel = {}
    for row in as_list((synth or {}).get("opponent_intel")):
        if not isinstance(row, dict):
            continue
        for key in (row.get("owner"), row.get("team")):
            if key:
                intel[str(key).strip().lower()] = row.get("paragraph")

    # The seat map is a DRAFT artifact -- rival "biggest hole" there is derived
    # from predicted keeper sets, and it becomes meaningless the moment real
    # rosters exist. Only attach it before the draft.
    pre_draft = ((state or {}).get("meta") or {}).get("league_status") == "pre_draft"
    seat_map = {}
    board_text = read_text(DRAFT_BOARD_PATH) if pre_draft else None
    if board_text:
        t = md_first_table(md_section(board_text, r"THE SEAT MAP"))
        if t:
            for row in t["rows"]:
                if len(row) < 4:
                    continue
                key = re.sub(r"\*|\(|\)", "", row[1]).strip().lower()
                seat_map[key] = {"qbs_kept": row[2], "biggest_hole": row[3],
                                 "slot": row[0].strip("* ")}

    def seat_for(owner, team_name):
        for key, v in seat_map.items():
            if owner and owner.lower() in key:
                return v
            if team_name and team_name.lower().split("(")[0].strip() in key:
                return v
        return None

    cards = []
    for rid_s, team in sorted(((k, v) for k, v in teams.items()
                               if isinstance(v, dict) and str(k).lstrip("-").isdigit()),
                              key=lambda kv: int(kv[0])):
        rid = int(rid_s)
        if rid == andrew_rid:
            continue
        st = standings.get(rid) or {}
        pr = pressure.get(rid_s) or pressure.get(rid) or {}
        mdl = model.get(rid_s) or model.get(str(rid)) or {}
        press = pr.get("pressure") or {}
        top = sorted(((k, v) for k, v in press.items() if isinstance(v, (int, float))),
                     key=lambda kv: -kv[1])
        cards.append({
            "roster_id": rid,
            "owner": team.get("owner"),
            "team_name": team.get("team_name"),
            "record": "%s-%s-%s" % (st.get("wins", 0), st.get("losses", 0),
                                    st.get("ties", 0)),
            "pf": st.get("pf"), "pa": st.get("pa"),
            "waiver_priority": team.get("waiver_priority") or st.get("waiver_priority"),
            "positional_counts": team.get("positional_counts") or {},
            "injuries": team.get("injuries") or [],
            "starters": team.get("starters") or [],
            "bench": team.get("bench") or [],
            "pressure": press,
            "pressure_top": top[:3],
            "pressure_confidence": pr.get("confidence"),
            "pressure_evidence": [b.get("evidence") for b in
                                  (pr.get("pressure_breakdown") or [])
                                  if b.get("evidence")],
            "need_positions": pr.get("need_positions") or [],
            "surplus_positions": pr.get("surplus_positions") or [],
            "vulnerable_starters": pr.get("vulnerable_starters") or [],
            "data_gaps": pr.get("data_gaps") or [],
            "predicted_claims": mdl.get("predicted_claims") or [],
            "trade_appetite": mdl.get("trade_appetite"),
            "exploitable_weakness": (mdl.get("exploitable_weakness")
                                     or mdl.get("weakness")),
            "model_confidence": mdl.get("confidence"),
            "seat": seat_for(team.get("owner"), team.get("team_name")),
            "intel": (intel.get(str(team.get("owner") or "").lower())
                      or intel.get(str(team.get("team_name") or "").lower())),
            "blocking_opportunity": mdl.get("blocking_opportunity"),
        })

    return {
        "cards": cards,
        "has_model": bool(model),
        "has_pressure": bool(pressure),
        "seat_note": ("DRAFT-DAY HOLE and QBs-kept come from the seat map in "
                      "draft_board_2026.md, computed from each rival's predicted "
                      "keeper set. Only Glizzy Guzzler has actually locked keepers "
                      "in Sleeper, so for the other eight this is a strong "
                      "prediction, not a fact."),
        "model_note": ("opponent_model is empty in the state file. It is written "
                       "by the weekly.js opponent agents and folded in by "
                       "merge_state.py; run those and rebuild to fill in predicted "
                       "waiver targets, trade appetite and exploitable weakness."),
        "pressure_note": (
            "Pressure is computed live from the roster + injury data in the state "
            "file by analysis/opponent_pressure.py."
            + (" Before Week 1 there is no scoring or role-signal input, so every "
               "score is low-confidence by construction." if pre_draft else
               " Scores renormalise over whichever components have data, so they "
               "are not comparable across a week where recent scoring or role "
               "signals started being supplied.")),
    }


# ---------------------------------------------------------------------------
# WAIVERS tab
# ---------------------------------------------------------------------------

def build_waivers(cfg, state, synth, warnings):
    fa = (state or {}).get("free_agents")
    fa = fa if isinstance(fa, dict) else {}
    meta = (state or {}).get("meta") or {}
    waiver = meta.get("waiver") or {}
    cfg_waiver = (cfg or {}).get("waivers") or {}
    claims = (as_list((synth or {}).get("waiver_claims"))
              or as_list((state or {}).get("waiver_claims")))
    claims = sorted([c for c in claims if isinstance(c, dict)],
                    key=lambda c: c.get("order") or 999)
    drops = (as_list((synth or {}).get("drop_candidates"))
             or as_list((state or {}).get("drop_candidates")))
    drops = sorted([c for c in drops if isinstance(c, dict)],
                   key=lambda c: c.get("rank") or 999)

    order = []
    for row in as_list((state or {}).get("waiver_order")):
        if not isinstance(row, dict):
            continue
        order.append({
            "priority": row.get("waiver_priority"),
            "roster_id": row.get("roster_id"),
            "owner": row.get("owner"),
            "is_andrew": row.get("roster_id") == (((cfg or {}).get("andrew") or {}).get("roster_id") or 2),
        })

    return {
        "claims": claims,
        "drops": drops,
        "has_claim_sheet": bool(claims),
        "claim_note": ("No claim sheet exists yet. It is produced by the opus "
                       "waiver-contention agent in weekly.js (backed by "
                       "analysis/waiver_contention.py) and only becomes meaningful "
                       "once the season is under way and rosters are real. Note "
                       "that merge_state.py does NOT copy it into week_N.json -- "
                       "dump the full synthesis object to "
                       "state/week_N.synthesis.json (or pass --synthesis) and it "
                       "will appear here."),
        "order": order,
        "andrew_position": (state or {}).get("andrew_waiver_position"),
        "teams_ahead": (state or {}).get("teams_picking_ahead_of_andrew") or [],
        "type": waiver.get("type") or cfg_waiver.get("type"),
        "is_faab": waiver.get("is_faab", cfg_waiver.get("is_faab")),
        "type_evidence": cfg_waiver.get("_evidence_summary"),
        "process_day": waiver.get("process_day") or cfg_waiver.get("waiver_day_name"),
        "day_verified": cfg_waiver.get("waiver_day_name_verified", False),
        "day_note": cfg_waiver.get("_day_note"),
        "deadline_guidance": (waiver.get("submit_deadline_guidance")
                              or cfg_waiver.get("run_deadline_guidance")),
        "priority_rule": cfg_waiver.get("priority_rule"),
        "free_agents": fa.get("confirmed_available_known_players") or [],
        "available_defenses": fa.get("available_defenses") or [],
        "fa_count": fa.get("count"),
        "fa_gate": fa.get("_gate"),
        "fa_caveat": fa.get("caveat"),
        "trending_adds": (state or {}).get("trending_adds") or [],
        "keeper_add_cost_round": ((cfg or {}).get("keeper_rules") or {}).get(
            "undrafted_pickup_cost_round"),
    }


# ---------------------------------------------------------------------------
# TRADES tab
# ---------------------------------------------------------------------------

def build_trades(cfg, state, synth, warnings):
    offers = [o for o in (as_list((synth or {}).get("trade_board"))
                          or as_list((state or {}).get("trade_board"))
                          or as_list((state or {}).get("trade_offers")))
              if isinstance(o, dict)]
    model = (state or {}).get("opponent_model") or {}
    appetites = []
    teams = (state or {}).get("teams")
    teams = teams if isinstance(teams, dict) else {}
    if not isinstance(model, dict):
        model = {}
    for rid, blk in sorted(((k, v) for k, v in model.items()
                            if isinstance(v, dict) and str(k).lstrip("-").isdigit()),
                           key=lambda kv: int(kv[0])):
        appetites.append({
            "roster_id": int(rid),
            "owner": (teams.get(str(rid)) or {}).get("owner"),
            "trade_appetite": blk.get("trade_appetite"),
            "confidence": blk.get("confidence"),
        })
    meta = (state or {}).get("meta") or {}
    deadline = meta.get("trade_deadline_week")
    wk = meta.get("week")
    weeks_left = (deadline - wk) if isinstance(deadline, int) and isinstance(wk, int) and wk > 0 else None
    return {
        "offers": offers,
        "has_offers": bool(offers),
        "appetites": appetites,
        "trade_deadline_week": deadline,
        "weeks_to_deadline": weeks_left,
        "phase": (meta.get("season_phase") or {}).get("name"),
        "note": ("The trade board is written by the opus trade agent in "
                 "weekly.js. It needs a real opponent_model (positional pressure "
                 "with actual scoring behind it) to produce sendable offers, so "
                 "it stays empty until the season starts. Pre-draft, the lever "
                 "that exists instead is draft-pick trading -- see the DRAFT tab. "
                 "merge_state.py does not copy trade_board into week_N.json; dump "
                 "the full synthesis object to state/week_N.synthesis.json to "
                 "surface it here."),
        "pick_trading_allowed": ((cfg or {}).get("trading") or {}).get(
            "draft_pick_trading", True),
    }


# ---------------------------------------------------------------------------
# KEEPERS tab
# ---------------------------------------------------------------------------

def _watchlist(state, synth):
    """state.keeper_equity (plan schema) and synthesis.keeper_equity_watchlist
    (weekly.js schema) carry the same idea under different key names. Normalise
    once here so the renderer only knows one shape."""
    rows = (as_list((state or {}).get("keeper_equity"))
            or as_list((synth or {}).get("keeper_equity_watchlist")))
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "player": r.get("player"),
            "acquired": r.get("acquired") or r.get("where"),
            "keeper_cost_2027": r.get("keeper_cost_2027") or r.get("cost_2027"),
            "projected_value": r.get("projected_value"),
            "surplus": r.get("surplus"),
            "note": r.get("consecutive_year_cap_note") or r.get("note"),
        })
    return out


def build_keepers(cfg, state, synth, warnings):
    if ANALYSIS_DIR not in sys.path:
        sys.path.insert(0, ANALYSIS_DIR)
    board_2027, board_2026 = [], []
    try:
        import keeper_equity  # noqa
    except Exception as exc:
        warnings.append("KEEPERS: could not import keeper_equity.py (%s)" % exc)
        keeper_equity = None
    if keeper_equity is not None:
        slot = ((cfg or {}).get("andrew") or {}).get("draft_slot")
        try:
            rows26 = keeper_equity.andrew_roster_from_config(
                config_path=CONFIG_PATH, season=2026)
            board_2026 = keeper_equity.build_keeper_board(rows26, draft_slot=slot)
            rows27 = keeper_equity.andrew_roster_from_config(
                config_path=CONFIG_PATH, season=2027)
            board_2027 = keeper_equity.build_keeper_board(rows27, draft_slot=slot)
            # build_keeper_board drops the cost_basis_unknown marker that
            # andrew_roster_from_config sets. Join it back, or the 2027 board
            # quotes a carried-forward cost for players who are going straight
            # back into the draft and have no 2027 cost yet.
            basis = {r.get("player_id"): r for r in rows27}
            for row in board_2027:
                src = basis.get(row.get("player_id")) or {}
                unknown = src.get("cost_basis_unknown")
                row["cost_basis_unknown"] = unknown
                row["cost_basis"] = src.get("cost_basis")
                if unknown:
                    row["keeper_cost_2027"] = None
                    row["keeper_cost_round"] = None
                    row["forfeits_overall_pick"] = None
        except Exception as exc:
            warnings.append("KEEPERS: keeper_equity raised %s: %s"
                            % (type(exc).__name__, exc))

    carried = [r for r in board_2027 if not r.get("cost_basis_unknown")]
    unknown = [r for r in board_2027 if r.get("cost_basis_unknown")]

    rules = (cfg or {}).get("keeper_rules") or {}
    return {
        "rules": rules,
        "board_2026": board_2026,
        "carried_2027": carried,
        "unknown_2027": unknown,
        "state_keeper_equity": _watchlist(state, synth),
        "projection_note": ("No 2027 projections have been supplied to "
                            "keeper_equity.py, so every surplus reads 'unknown' "
                            "rather than being guessed. Surplus becomes real the "
                            "moment rest-of-season projections are fed in "
                            "mid-season."),
        "waiver_add_note": ("Every in-season waiver add costs a %s to keep in "
                            "2027. That is the single biggest edge in this league "
                            "-- a claimed breakout is worth far more than identical "
                            "production from a round-3 draft pick."
                            % ("R%d" % rules["undrafted_pickup_cost_round"]
                               if rules.get("undrafted_pickup_cost_round") else
                               "12th-round pick")),
    }


# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

def collect(week=None, synthesis_path=None):
    warnings = []
    state_path = find_state(week)
    state = as_dict(read_json(state_path), state_path, warnings) if state_path else None
    if state is None:
        warnings.append(
            "No usable state file found in %s. Run state_builder.py first; the "
            "dashboard is rendering structure only." % STATE_DIR)
        state = {}
    cfg = as_dict(read_json(CONFIG_PATH), CONFIG_PATH, warnings)
    if cfg is None:
        warnings.append("league_config.json missing or unparseable at %s" % CONFIG_PATH)
        cfg = {}

    meta = state.get("meta") or {}
    wk = meta.get("week", week)

    synth_path, synth = find_synthesis(wk, synthesis_path)
    synth = as_dict(synth, synth_path or "synthesis", warnings)
    if synthesis_path and synth is None:
        warnings.append("--synthesis %s could not be read or parsed." % synthesis_path)
    if synth is not None and not any(
            k in synth for k in ("waiver_claims", "trade_board", "action_card")):
        warnings.append(
            "%s is the state-only shape (merge_state's input). The action card, "
            "claim sheet and trade board are not in it, so those panels stay "
            "empty. Dump the FULL synthesis agent object there to populate them."
            % synth_path)

    report_path = os.path.join(REPORTS_DIR, "week_%s.md" % wk)
    report = read_text(report_path)

    data = {
        "build": {
            "generated_at": _now_iso(),
            "builder": "build_dashboard.py",
            "state_file": state_path,
            "state_generated_at": meta.get("generated_at"),
            "week": wk,
            "season": meta.get("season") or ((cfg.get("league") or {}).get("season")),
            "season_phase": meta.get("season_phase") or {},
            "league_status": meta.get("league_status"),
            "league_name": (cfg.get("league") or {}).get("name"),
            "degraded": meta.get("degraded", False),
            "state_warnings": meta.get("warnings") or [],
            "sources": meta.get("sources") or {},
            "open_questions": state.get("open_questions") or [],
            "report_path": report_path if report else None,
            "synthesis_file": synth_path,
        },
        "action_card": sorted(
            [a for a in as_list((synth or {}).get("action_card")) if isinstance(a, dict)],
            key=lambda a: a.get("rank") or 99),
        "standings": [r for r in as_list(state.get("standings")) if isinstance(r, dict)],
        "draft": build_draft(cfg, state, warnings),
        "my_team": build_my_team(cfg, state, synth, warnings),
        "opponents": build_opponents(cfg, state, synth, warnings),
        "waivers": build_waivers(cfg, state, synth, warnings),
        "trades": build_trades(cfg, state, synth, warnings),
        "keepers": build_keepers(cfg, state, synth, warnings),
        "report": report,
    }
    data["build"]["build_warnings"] = warnings
    return data


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>Sunday Scaries &mdash; Command Dashboard</title>
<style>
:root{
  --bg:#0b0f14; --panel:#151b23; --panel2:#1b232d; --line:#2a3441;
  --tx:#e7edf4; --mut:#93a1b1; --dim:#8090a0;
  --grn:#3fb950; --red:#f85149; --amb:#e3b341; --blu:#58a6ff; --pur:#bc8cff;
  --tap:46px;
}
*{box-sizing:border-box;-webkit-text-size-adjust:100%}
html,body{margin:0;padding:0;background:var(--bg);color:var(--tx);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
body{padding-bottom:56px;overflow-x:hidden}
.wrap{max-width:940px;margin:0 auto;padding:0 12px}
a{color:var(--blu)}
h1,h2,h3{margin:0;font-weight:650;line-height:1.25}
code{background:#0d1117;border:1px solid var(--line);border-radius:4px;
  padding:1px 5px;font-size:.85em;word-break:break-word}
strong{color:#fff;font-weight:650}

/* ---------- header ---------- */
header{background:linear-gradient(180deg,#131a22,#0b0f14);
  border-bottom:1px solid var(--line);padding:14px 0 10px}
.hd-top{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.hd-top h1{font-size:19px;letter-spacing:.2px}
.hd-sub{color:var(--mut);font-size:12.5px;margin-top:5px;line-height:1.45}
.stamp{display:inline-flex;align-items:center;gap:6px;background:#0d1117;
  border:1px solid var(--line);border-radius:999px;padding:3px 10px;
  font-size:11.5px;color:var(--mut);margin-top:8px;margin-right:6px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--grn);flex:none}
.dot.warn{background:var(--amb)} .dot.bad{background:var(--red)}

/* ---------- tabs ---------- */
nav{position:sticky;top:0;z-index:20;background:rgba(11,15,20,.97);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.tabs{display:flex;gap:6px;overflow-x:auto;padding:8px 12px;
  max-width:940px;margin:0 auto;-webkit-overflow-scrolling:touch;
  scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;min-height:var(--tap);padding:0 15px;border-radius:10px;
  border:1px solid var(--line);background:var(--panel);color:var(--mut);
  font-size:13.5px;font-weight:650;letter-spacing:.6px;cursor:pointer;
  display:inline-flex;align-items:center;gap:6px;
  -webkit-tap-highlight-color:transparent;touch-action:manipulation}
.tab:active{transform:scale(.97)}
.tab[aria-selected="true"]{background:#1d3a5c;border-color:#2f6cb0;color:#fff}
.tab .pill{background:#0d1117;border:1px solid var(--line);border-radius:999px;
  padding:0 6px;font-size:10.5px;color:var(--mut);font-weight:600}
.tab[aria-selected="true"] .pill{color:#cfe3ff;border-color:#2f6cb0}

/* ---------- panels ---------- */
section[role=tabpanel]{display:none;padding:14px 0 30px}
section[role=tabpanel].on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:13px;margin:0 0 12px;overflow-wrap:break-word;min-width:0}
.card h2{font-size:14px;letter-spacing:.7px;text-transform:uppercase;
  color:var(--mut);margin-bottom:10px;display:flex;align-items:center;
  gap:8px;flex-wrap:wrap}
.card h3{font-size:14.5px;margin:14px 0 7px}
.card h3:first-child{margin-top:0}
p{margin:0 0 9px} p:last-child{margin-bottom:0}
.mut{color:var(--mut)} .dim{color:var(--dim);font-size:12.5px}
.small{font-size:12.5px}

.badge{display:inline-block;border-radius:6px;padding:2px 7px;font-size:11px;
  font-weight:700;letter-spacing:.4px;white-space:nowrap;border:1px solid}
.b-grn{color:#8ee79b;border-color:#2b6a37;background:#12281a}
.b-red{color:#ffb1ab;border-color:#79302c;background:#2b1513}
.b-amb{color:#f5d98a;border-color:#7a601f;background:#2a2210}
.b-blu{color:#a9d1ff;border-color:#2b5580;background:#111f30}
.b-pur{color:#dcc4ff;border-color:#5b3f86;background:#1f1630}
.b-gry{color:var(--mut);border-color:var(--line);background:#10161d}

.nodata{border:1px dashed #46525f;background:#12181f;border-radius:10px;
  padding:12px;color:var(--mut);font-size:13.5px}
.nodata b{display:block;color:var(--amb);font-size:11.5px;letter-spacing:1px;
  text-transform:uppercase;margin-bottom:6px}
.warnbox{border:1px solid #6b4a10;background:#221a09;border-radius:10px;
  padding:11px;font-size:13px;color:#f0dcae;margin-bottom:12px}
.warnbox b{color:var(--amb);display:block;font-size:11.5px;letter-spacing:1px;
  text-transform:uppercase;margin-bottom:6px}

/* ---------- responsive tables: no horizontal scroll, ever ---------- */
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);
  vertical-align:top;word-break:break-word;overflow-wrap:anywhere}
th{color:var(--mut);font-size:11.5px;letter-spacing:.6px;text-transform:uppercase;
  font-weight:650}
tbody tr:last-child td{border-bottom:0}
@media (max-width:700px){
  table,thead,tbody,tr,td{display:block;width:100%}
  thead{position:absolute;left:-9999px}
  tbody tr{border:1px solid var(--line);border-radius:10px;margin-bottom:9px;
    background:var(--panel2);padding:3px 0}
  td{border-bottom:1px solid #222c37;padding:7px 11px}
  tr td:last-child{border-bottom:0}
  td:before{content:attr(data-l);display:block;color:var(--dim);font-size:10.5px;
    letter-spacing:.7px;text-transform:uppercase;margin-bottom:2px}
  td[data-l=""]:before{display:none}
}

/* ---------- pick map ---------- */
.picks{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:7px}
.pk{border:1px solid var(--line);border-radius:10px;background:var(--panel2);
  padding:8px 6px;text-align:center}
.pk .rd{font-size:10.5px;color:var(--dim);letter-spacing:.6px}
.pk .ov{font-size:20px;font-weight:700;line-height:1.15}
.pk .st{font-size:10px;margin-top:3px;letter-spacing:.3px}
.pk.live{border-color:#2b6a37}.pk.live .ov{color:#8ee79b}
.pk.live .st{color:#5f9c6b}
.pk.dead{border-color:#79302c;background:#1d1211}.pk.dead .ov{color:#ff9d95}
.pk.dead .st{color:#c0736c}
.gapbar{display:flex;align-items:center;gap:8px;border:1px solid #7a601f;
  background:#241d0d;border-radius:9px;padding:8px 10px;margin:8px 0;font-size:13px}
.gapbar .n{font-size:17px;font-weight:700;color:var(--amb);flex:none}

.kv{display:flex;flex-wrap:wrap;gap:7px;margin:9px 0}
.kv div{background:var(--panel2);border:1px solid var(--line);border-radius:9px;
  padding:7px 10px;font-size:12.5px;min-width:78px}
.kv span{display:block;color:var(--dim);font-size:10.5px;letter-spacing:.6px;
  text-transform:uppercase}
.kv b{font-size:16px;font-weight:700}

.slot{display:flex;align-items:center;gap:9px;padding:9px 4px;
  border-bottom:1px solid var(--line)}
.slot:last-child{border-bottom:0}
.slot .sl{flex:0 0 62px;font-size:10.5px;font-weight:700;letter-spacing:.6px;
  color:var(--mut);text-transform:uppercase}
.slot .nm{flex:1 1 auto;min-width:0}
.slot .nm b{display:block;font-size:14.5px;word-break:break-word}
.slot .nm .meta{color:var(--dim);font-size:11.5px}
.slot .rt{flex:0 0 auto;text-align:right;display:flex;flex-direction:column;
  align-items:flex-end;gap:3px}

.bars{margin-top:6px}
.bar{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12.5px}
.bar .lb{flex:0 0 38px;color:var(--mut);font-weight:650;font-size:11.5px}
.bar .tr{flex:1 1 auto;height:7px;background:#0d1117;border-radius:4px;
  border:1px solid var(--line);overflow:hidden}
.bar .fl{height:100%;background:linear-gradient(90deg,#2f6cb0,#58a6ff)}
.bar .fl.hi{background:linear-gradient(90deg,#8a3a2e,#f85149)}
.bar .fl.md{background:linear-gradient(90deg,#7a601f,#e3b341)}
.bar .vl{flex:0 0 34px;text-align:right;color:var(--mut);font-variant-numeric:tabular-nums}

details{border:1px solid var(--line);border-radius:10px;background:var(--panel2);
  margin:8px 0;overflow:hidden}
summary{padding:11px 12px;min-height:var(--tap);display:flex;align-items:center;
  cursor:pointer;font-size:13.5px;font-weight:650;color:var(--tx);
  list-style:none;-webkit-tap-highlight-color:transparent}
summary::-webkit-details-marker{display:none}
summary:before{content:"›";display:inline-block;margin-right:9px;color:var(--blu);
  font-size:19px;line-height:1;transform:rotate(0);transition:transform .15s}
details[open] summary:before{transform:rotate(90deg)}
details .bd{padding:0 12px 12px;font-size:13.5px}
.opp{margin-bottom:10px}
.opp .hd{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.opp .hd b{font-size:15px}
ul.tight{margin:6px 0;padding-left:19px} ul.tight li{margin:3px 0}
.rulelist{counter-reset:r;list-style:none;padding:0;margin:0}
.rulelist li{border-bottom:1px solid var(--line);padding:9px 0;font-size:13.5px}
.rulelist li:last-child{border-bottom:0}
.mono{font-variant-numeric:tabular-nums}
footer{color:var(--dim);font-size:11.5px;text-align:center;padding:18px 12px 26px;
  line-height:1.6}
.hr{height:1px;background:var(--line);margin:13px 0}
.act{background:linear-gradient(180deg,#1a2a1c,#141d16);border:1px solid #2b6a37;
  border-radius:12px;padding:12px;margin:12px 0 0}
.act h2{font-size:12px;letter-spacing:1px;text-transform:uppercase;color:#8ee79b;
  margin-bottom:8px}
.act ol{margin:0;padding-left:22px}
.act li{padding:5px 0;font-size:14px;border-bottom:1px solid #22331f}
.act li:last-child{border-bottom:0}
.act .dl{display:block;color:var(--amb);font-size:11.5px;margin-top:2px}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="hd-top"><h1 id="hTitle">Sunday Scaries</h1><span class="badge b-blu" id="hPhase">&nbsp;</span></div>
  <div class="hd-sub" id="hSub"></div>
  <div id="hStamps"></div>
</div></header>

<div class="wrap"><div id="actionCard"></div></div>

<nav><div class="tabs" id="tabs" role="tablist"></div></nav>

<main class="wrap" id="main"></main>

<footer id="foot"></footer>

<script id="payload" type="application/json">%%DATA%%</script>
<script>
"use strict";
var D = JSON.parse(document.getElementById("payload").textContent);

/* ---------- tiny helpers ---------- */
function esc(s){return String(s==null?"":s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function md(s){                       /* inline markdown from the board doc */
  var t = esc(s);
  t = t.replace(/`([^`]+)`/g,"<code>$1</code>");
  t = t.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>");
  t = t.replace(/(^|[\s(])\*([^*]+)\*/g,"$1<em>$2</em>");
  return t;
}
function el(tag,cls,htmlStr){var e=document.createElement(tag);
  if(cls)e.className=cls; if(htmlStr!=null)e.innerHTML=htmlStr; return e;}
function card(title,extra){var c=el("div","card");
  if(title){var h=el("h2",null,esc(title)); if(extra)h.insertAdjacentHTML("beforeend"," "+extra);
  c.appendChild(h);} return c;}
function nodata(label,msg){return '<div class="nodata"><b>'+esc(label)+
  '</b>'+esc(msg)+'</div>';}
function num(v,d){ if(v==null||v==="")return "&mdash;";
  var n=Number(v); return isNaN(n)?esc(v):n.toFixed(d==null?1:d);}
function pct(v){return v==null?"&mdash;":Math.round(Number(v)*100)+"%";}

/* responsive table from {headers, rows} or from explicit arrays */
function table(headers,rows,opts){
  opts=opts||{};
  if(!rows||!rows.length) return "";
  var h="<table><thead><tr>";
  headers.forEach(function(x){h+="<th>"+md(x)+"</th>";});
  h+="</tr></thead><tbody>";
  rows.forEach(function(r){
    h+="<tr>";
    r.forEach(function(c,i){
      h+='<td data-l="'+esc(headers[i]||"")+'">'+(opts.raw?esc(c):md(c))+"</td>";
    });
    h+="</tr>";
  });
  return h+"</tbody></table>";
}
function mdTable(t){ return t&&t.rows&&t.rows.length ? table(t.headers,t.rows) : ""; }

function bar(label,val,thresholds){
  var v = val==null?0:Number(val);
  var cls = v>=0.66?"hi":(v>=0.33?"md":"");
  return '<div class="bar"><div class="lb">'+esc(label)+'</div>'+
    '<div class="tr"><div class="fl '+cls+'" style="width:'+
    Math.max(2,Math.round(v*100))+'%"></div></div>'+
    '<div class="vl">'+(val==null?"&mdash;":v.toFixed(2))+'</div></div>';
}

/* ---------- header ---------- */
(function(){
  var b=D.build||{};
  document.getElementById("hTitle").textContent =
    (b.league_name||"Sunday Scaries")+" "+(b.season||"");
  var ph=(b.season_phase||{}).name||b.league_status||"";
  var phEl=document.getElementById("hPhase");
  phEl.textContent = ph? ph.replace(/_/g," ").toUpperCase() : "";
  if(!ph) phEl.style.display="none";
  var sub=[];
  if(b.league_status==="pre_draft") sub.push("Pre-draft. Rosters below are last season's carryover; only keepers survive Aug 28.");
  if((b.season_phase||{}).default_posture) sub.push((b.season_phase||{}).default_posture);
  document.getElementById("hSub").innerHTML = sub.map(esc).join(" ");
  var s=document.getElementById("hStamps"), parts=[];
  parts.push(['<span class="dot"></span>',"data as of "+esc(b.state_generated_at||"unknown")]);
  parts.push(['<span class="dot '+(b.degraded?"warn":"")+'"></span>',
    "week "+(b.week==null?"?":b.week)+(b.degraded?" · degraded":"")]);
  parts.push(['<span class="dot"></span>',"built "+esc(b.generated_at||"")]);
  s.innerHTML = parts.map(function(p){return '<span class="stamp">'+p[0]+p[1]+"</span>";}).join("");
})();

/* ---------- action card (above the tabs, on every tab) ---------- *
 * Deliberately absent rather than empty when there is nothing to do -- an
 * empty green box every week would train the eye to ignore it.            */
(function(){
  var a=D.action_card||[];
  if(!a.length) return;
  document.getElementById("actionCard").innerHTML =
    '<div class="act"><h2>Do this first &mdash; week '+esc((D.build||{}).week)+'</h2><ol>'+
    a.map(function(x){return "<li>"+md(x.action||"")+
      (x.deadline?'<span class="dl">'+esc(x.deadline)+"</span>":"")+"</li>";}).join("")+
    "</ol></div>";
})();

/* ---------- TAB: DRAFT ---------- */
function tabDraft(){
  var f=document.createDocumentFragment(), d=D.draft||{};
  var c=card("Draft");
  var days = d.days_until;
  var kv='<div class="kv">'+
    '<div><span>Slot</span><b>'+esc(d.slot||"?")+'</b></div>'+
    '<div><span>Live picks</span><b>'+((d.live_overalls||[]).length)+'</b></div>'+
    '<div><span>Forfeited</span><b>'+((d.forfeited||[]).length)+'</b></div>'+
    '<div><span>Days out</span><b>'+(days==null?"&mdash;":Math.max(0,Math.ceil(days)))+'</b></div>'+
    '</div>';
  c.insertAdjacentHTML("beforeend", kv);
  if(d.draft_datetime_et) c.insertAdjacentHTML("beforeend",
    '<p class="dim">'+esc(d.draft_datetime_et.replace("T"," ").slice(0,16))+
    ' ET &middot; '+esc(d.num_teams||"?")+' teams &middot; '+esc(d.rounds||"?")+
    ' rounds &middot; snake</p>');
  f.appendChild(c);

  /* pick map */
  var pm=card("Pick map",'<span class="badge b-gry">slot '+esc(d.slot)+'</span>');
  var g='<div class="picks">';
  (d.picks||[]).forEach(function(p){
    var live = p.status==="live";
    g+='<div class="pk '+(live?"live":"dead")+'"><div class="rd">R'+esc(p.round)+
      '</div><div class="ov">'+esc(p.overall)+'</div><div class="st">'+
      (live?"LIVE":"FORFEIT")+'</div></div>';
  });
  g+="</div>";
  pm.insertAdjacentHTML("beforeend",g);
  var ff=(d.forfeited||[]);
  if(ff.length){
    pm.insertAdjacentHTML("beforeend",'<div class="hr"></div>');
    pm.insertAdjacentHTML("beforeend", table(["Round","Pick","Lost to"],
      ff.map(function(p){return ["R"+p.round,"p"+p.overall,p.reason||"keeper"];})));
  }
  var dz=(d.gaps||[]).filter(function(g){return g.dead_zone;});
  if(dz.length){
    pm.insertAdjacentHTML("beforeend",'<h3>Dead zones &mdash; '+dz.length+
      ' &times; '+dz[0].nominal+' picks</h3>');
    dz.forEach(function(g){
      pm.insertAdjacentHTML("beforeend",'<div class="gapbar"><div class="n">'+
        g.nominal+'</div><div>p'+g.from+' &rarr; p'+g.to+
        ' &mdash; nothing you need can be planned for <em>after</em> this gap.</div></div>');
    });
  }
  f.appendChild(pm);

  /* keepers */
  var kc=card("Keepers","");
  if((d.keepers||[]).length){
    if(d.keeper_status) kc.insertAdjacentHTML("beforeend",
      '<p class="dim">'+esc(d.keeper_status)+'</p>');
    (d.keepers||[]).forEach(function(k){
      var yr = k.years_remaining_after;
      kc.insertAdjacentHTML("beforeend",
        '<div class="slot"><div class="sl">'+esc(k.pos)+'</div>'+
        '<div class="nm"><b>'+esc(k.name)+'</b><div class="meta">costs p'+
        esc(k.forfeits_overall_pick)+' &middot; year '+esc(k.consecutive_years_if_kept)+
        ' of 3'+(k.final_eligible_year_if_kept?" &middot; final eligible "+
        esc(k.final_eligible_year_if_kept):"")+'</div></div>'+
        '<div class="rt"><span class="badge b-pur">R'+esc(k.cost_round)+'</span>'+
        (yr!=null?'<span class="badge '+(yr<=1?"b-amb":"b-gry")+'">'+yr+
          ' yr left</span>':'')+'</div></div>');
    });
  } else {
    kc.insertAdjacentHTML("beforeend", nodata("no keeper plan",
      "league_config.andrew.keeper_plan.keeping is empty."));
  }
  if((d.passed_over||[]).length){
    kc.insertAdjacentHTML("beforeend","<h3>Passed over &mdash; back in the pool</h3>");
    kc.insertAdjacentHTML("beforeend", table(["Player","Cost","Why not"],
      d.passed_over.map(function(p){return [p.name+" ("+p.pos+")","R"+p.cost_round,p.note||""];})));
  }
  f.appendChild(kc);

  /* roster holes */
  var n=d.needs||{};
  var rc=card("Roster holes after keepers");
  var un=(n.unfilled_starters||[]);
  rc.insertAdjacentHTML("beforeend",'<div class="kv">'+
    '<div><span>Starters to fill</span><b>'+un.length+'</b></div>'+
    '<div><span>Bench</span><b>'+esc(n.bench_slots)+'</b></div>'+
    '<div><span>Spots</span><b>'+esc(n.spots_to_fill)+'</b></div>'+
    '<div><span>Picks</span><b>'+esc(n.picks_available)+'</b></div></div>');
  if(un.length) rc.insertAdjacentHTML("beforeend",
    '<p>'+un.map(function(s){return '<span class="badge b-red" style="margin:2px 3px 2px 0">'+
      esc(s)+'</span>';}).join("")+'</p>');
  if((n.filled_by_keepers||[]).length) rc.insertAdjacentHTML("beforeend",
    '<p class="small mut">Filled by keepers: '+n.filled_by_keepers.map(function(x){
      return esc(x.slot)+" = "+esc(x.player);}).join(" &middot; ")+'</p>');
  if(n.spots_to_fill===n.picks_available) rc.insertAdjacentHTML("beforeend",
    '<p class="small mut">'+n.picks_available+' picks for '+n.spots_to_fill+
    ' spots &mdash; zero margin for a wasted selection.</p>');
  f.appendChild(rc);

  /* the board */
  var b=d.board||{};
  if(!b.available){
    var pc=card("Draft board");
    pc.insertAdjacentHTML("beforeend", nodata("placeholder", b.note||
      "draft_board_2026.md not found."));
    f.appendChild(pc);
    return f;
  }
  if((b.thirty_second||[]).length){
    var tc=card("The 30-second version");
    tc.insertAdjacentHTML("beforeend","<div>"+b.thirty_second.map(function(l){
      return '<div style="padding:7px 0;border-bottom:1px solid var(--line)">'+md(l)+"</div>";
    }).join("")+"</div>");
    f.appendChild(tc);
  }
  if(b.pick_targets){
    var ptc=card("Pick-by-pick targets");
    ptc.insertAdjacentHTML("beforeend", mdTable(b.pick_targets));
    f.appendChild(ptc);
  }
  if(b.tiers){
    var tt=card("Value tiers");
    tt.insertAdjacentHTML("beforeend", mdTable(b.tiers));
    f.appendChild(tt);
  }
  if(b.checklist||(b.dead_zone_notes||[]).length){
    var dc=card("Dead-zone planning");
    if(b.checklist) dc.insertAdjacentHTML("beforeend", mdTable(b.checklist));
    (b.dead_zone_notes||[]).forEach(function(s){
      dc.insertAdjacentHTML("beforeend",'<details><summary>'+md(s.title)+
        '</summary><div class="bd">'+(s.body||[]).map(function(p){
          return "<p>"+md(p)+"</p>";}).join("")+'</div></details>');
    });
    f.appendChild(dc);
  }
  if(b.real_waits||b.true_pick_map||b.depletion){
    var wc=card("Real waits (live picks, not nominal)");
    wc.insertAdjacentHTML("beforeend", mdTable(b.real_waits||b.true_pick_map));
    if(b.depletion) wc.insertAdjacentHTML("beforeend",
      '<details><summary>Round-by-round keeper depletion</summary><div class="bd">'+
      mdTable(b.depletion)+'</div></details>');
    if(b.true_pick_map && b.real_waits) wc.insertAdjacentHTML("beforeend",
      '<details><summary>Live picks between each of your selections</summary>'+
      '<div class="bd">'+mdTable(b.true_pick_map)+'</div></details>');
    f.appendChild(wc);
  }
  if((b.rules||[]).length||b.pivot_triggers){
    var rc2=card("Draft-day rules");
    var groups={};
    (b.rules||[]).forEach(function(r){(groups[r.group]=groups[r.group]||[]).push(r.text);});
    Object.keys(groups).forEach(function(g){
      rc2.insertAdjacentHTML("beforeend","<h3>"+esc(g)+"</h3><ul class='rulelist'>"+
        groups[g].map(function(t){return "<li>"+md(t)+"</li>";}).join("")+"</ul>");
    });
    if(b.pivot_triggers) rc2.insertAdjacentHTML("beforeend",
      "<h3>Pivot triggers</h3>"+mdTable(b.pivot_triggers));
    f.appendChild(rc2);
  }
  if((b.panics||[]).length){
    var pcx=card("Panic buttons");
    b.panics.forEach(function(s){
      pcx.insertAdjacentHTML("beforeend",'<details><summary>'+md(s.title)+
        '</summary><div class="bd">'+(s.body||[]).map(function(p){
          return "<p>"+md(p)+"</p>";}).join("")+'</div></details>');
    });
    f.appendChild(pcx);
  }
  if((b.scenarios||[]).length){
    var sc=card("Mock drafts");
    b.scenarios.forEach(function(s){
      sc.insertAdjacentHTML("beforeend",'<details><summary>'+md(s.name)+
        '</summary><div class="bd">'+table(["Pick","Take"],
          s.picks.map(function(p){return ["p"+p.pick,p.take];}))+'</div></details>');
    });
    f.appendChild(sc);
  }
  if(b.one_paragraph){
    var oc=card("The one-paragraph plan");
    oc.insertAdjacentHTML("beforeend","<p>"+md(b.one_paragraph)+"</p>");
    f.appendChild(oc);
  }
  if((b.qb_answer||[]).length){
    var qc=card("The QB question");
    if(b.qb_headline) qc.insertAdjacentHTML("beforeend","<h3>"+md(b.qb_headline)+"</h3>");
    b.qb_answer.forEach(function(p){qc.insertAdjacentHTML("beforeend","<p>"+md(p)+"</p>");});
    f.appendChild(qc);
  }
  return f;
}

/* ---------- TAB: MY TEAM ---------- */
function injBadge(s){
  if(!s) return "";
  var cls = /out|ir|doubtful|pup|suspend/i.test(s)?"b-red":"b-amb";
  return '<span class="badge '+cls+'">'+esc(s)+'</span>';
}
function playerRow(p,slot){
  var badges="";
  if(p.keeper) badges+='<span class="badge b-pur">KEEP R'+esc(p.keeper_cost_round)+'</span>';
  else if(p.keeper_cost_round!=null && p.keeper_eligible!==false)
    badges+='<span class="badge b-gry">R'+esc(p.keeper_cost_round)+'</span>';
  else if(p.keeper_eligible===false)
    badges+='<span class="badge b-gry">R1 &mdash; ineligible</span>';
  badges+=injBadge(p.injury_status);
  if(p.keeper && p.years_remaining_after!=null)
    badges+='<span class="badge '+(p.years_remaining_after<=1?"b-amb":"b-gry")+'">'+
      p.years_remaining_after+' yr left</span>';
  var meta=[p.pos,p.team||"FA"].filter(Boolean).join(" &middot; ");
  if(p.keeper_flag) meta+=' &middot; <span style="color:var(--amb)">'+esc(p.keeper_flag)+"</span>";
  return '<div class="slot"><div class="sl">'+esc(slot||p.pos||"")+'</div>'+
    '<div class="nm"><b>'+esc(p.name||p.player_id)+'</b><div class="meta">'+meta+
    '</div></div><div class="rt">'+badges+'</div></div>';
}
function tabMyTeam(){
  var f=document.createDocumentFragment(), t=D.my_team||{};
  if(!t.available){
    var c0=card("My team");
    c0.insertAdjacentHTML("beforeend", nodata("no roster", t.note||"Not in state."));
    f.appendChild(c0); return f;
  }
  var c=card("My team",'<span class="badge b-gry">roster '+esc(t.roster_id)+'</span>');
  c.insertAdjacentHTML("beforeend",'<p class="dim">'+esc(t.team_name||"(no team name set)")+
    ' &middot; '+esc(t.owner)+' &middot; waiver priority '+esc(t.waiver_priority)+'</p>');
  var pc=t.positional_counts||{}, kv='<div class="kv">';
  ["QB","RB","WR","TE","DEF"].forEach(function(p){
    if(pc[p]!=null) kv+='<div><span>'+p+'</span><b>'+pc[p]+'</b></div>';});
  c.insertAdjacentHTML("beforeend", kv+"</div>");
  if(t.lineup_note) c.insertAdjacentHTML("beforeend",
    '<div class="warnbox"><b>read this first</b>'+esc(t.lineup_note)+'</div>');
  f.appendChild(c);

  if((t.lineup_card||[]).length){
    var lc=card("Recommended lineup",'<span class="badge b-grn">this week</span>');
    lc.insertAdjacentHTML("beforeend", table(["Slot","Start","Why"],
      t.lineup_card.map(function(x){return [x.slot||"",x.player||"",x.reason||""];})));
    f.appendChild(lc);
  }
  var sc=card("Starting lineup",
    (t.lineup_card||[]).length?'<span class="badge b-gry">as set in Sleeper</span>':"");
  (t.starters||[]).forEach(function(p){
    sc.insertAdjacentHTML("beforeend", playerRow(p,p.slot));});
  f.appendChild(sc);

  var bc=card("Bench",'<span class="badge b-gry">'+((t.bench||[]).length)+'</span>');
  (t.bench||[]).forEach(function(p){bc.insertAdjacentHTML("beforeend", playerRow(p,p.pos));});
  f.appendChild(bc);

  if((t.injuries||[]).length){
    var ic=card("Injuries");
    ic.insertAdjacentHTML("beforeend", table(
      ["Player","Pos","Status","Detail","Starter"],
      t.injuries.map(function(i){return [i.player,i.pos,i.status,
        (i.body_part||"")+(i.practice?" / "+i.practice:""),i.is_starter?"YES":"bench"];})));
    f.appendChild(ic);
  }
  var byc=card("Bye coverage");
  var bw=t.bye_weeks||{};
  if(bw.status==="unknown"||!Object.keys(bw.by_position||{}).length){
    byc.insertAdjacentHTML("beforeend", nodata("no data",
      bw.reason||"2026 NFL bye weeks are not loaded, so bye coverage cannot be computed."));
  } else {
    byc.insertAdjacentHTML("beforeend", table(["Position","Bye weeks"],
      Object.keys(bw.by_position).map(function(k){
        return [k,(bw.by_position[k]||[]).join(", ")];})));
  }
  f.appendChild(byc);
  return f;
}

/* ---------- TAB: OPPONENTS ---------- */
function tabOpponents(){
  var f=document.createDocumentFragment(), o=D.opponents||{};
  var c=card("Rivals",'<span class="badge b-gry">'+((o.cards||[]).length)+'</span>');
  if(!o.has_model) c.insertAdjacentHTML("beforeend",
    nodata("no opponent model yet", o.model_note||""));
  if(o.has_pressure) c.insertAdjacentHTML("beforeend",
    '<p class="small mut">'+esc(o.pressure_note||"")+'</p>');
  if((o.cards||[]).some(function(x){return x.seat;})) c.insertAdjacentHTML("beforeend",
    '<p class="dim small">'+esc(o.seat_note||"")+'</p>');
  f.appendChild(c);

  (o.cards||[]).forEach(function(t){
    var cc=el("div","card opp");
    var hole = t.seat&&t.seat.biggest_hole ? t.seat.biggest_hole : null;
    cc.insertAdjacentHTML("beforeend",'<div class="hd"><b>'+
      esc(t.team_name||t.owner)+'</b>'+
      '<span class="badge b-gry">'+esc(t.owner)+'</span>'+
      '<span class="badge b-blu">'+esc(t.record)+'</span>'+
      '<span class="badge b-gry">wvr '+esc(t.waiver_priority)+'</span>'+
      ((t.injuries||[]).length?'<span class="badge b-red">'+t.injuries.length+
        ' inj</span>':'')+'</div>');
    var pcnt=t.positional_counts||{}, s=[];
    ["QB","RB","WR","TE","DEF"].forEach(function(p){
      if(pcnt[p]!=null) s.push(p+" "+pcnt[p]);});
    cc.insertAdjacentHTML("beforeend",'<p class="dim" style="margin-top:6px">'+
      esc(s.join(" · "))+(t.pf?" · PF "+num(t.pf):"")+'</p>');

    if(hole) cc.insertAdjacentHTML("beforeend",
      '<p class="small"><span class="badge b-amb">DRAFT-DAY HOLE</span> '+md(hole)+
      (t.seat.qbs_kept?' <span class="dim">(QBs kept: '+md(t.seat.qbs_kept)+')</span>':'')+'</p>');

    var press=t.pressure||{}, keys=Object.keys(press);
    if(keys.length){
      var any=keys.some(function(k){return Number(press[k])>0;});
      var h='<div class="bars">';
      ["QB","RB","WR","TE","DEF"].forEach(function(p){
        if(press[p]!=null) h+=bar(p,press[p]);});
      h+="</div>";
      cc.insertAdjacentHTML("beforeend",h);
      cc.insertAdjacentHTML("beforeend",'<p class="dim small">positional pressure &middot; confidence '+
        esc(t.pressure_confidence||"?")+(any?"":" &middot; all zero: no injuries, no scoring history yet")+'</p>');
    }
    if((t.vulnerable_starters||[]).length) cc.insertAdjacentHTML("beforeend",
      '<p class="small"><b>Vulnerable starters:</b> '+
      esc(t.vulnerable_starters.map(function(v){return v.player||v.name||v;}).join(", "))+'</p>');
    if((t.injuries||[]).length) cc.insertAdjacentHTML("beforeend",
      '<p class="small"><b>Injured:</b> '+t.injuries.map(function(i){
        return esc(i.player)+" ("+esc(i.pos)+", "+esc(i.status)+
        (i.is_starter?", STARTER":"")+")";}).join(", ")+'</p>');

    cc.insertAdjacentHTML("beforeend",'<div class="hr"></div>');
    if(t.intel) cc.insertAdjacentHTML("beforeend",'<p class="small">'+md(t.intel)+'</p>');
    cc.insertAdjacentHTML("beforeend",'<p class="small"><b>Predicted waiver targets</b><br>'+
      ((t.predicted_claims||[]).length
        ? t.predicted_claims.map(function(x){
            if(typeof x==="string") return esc(x);
            return esc(x.player||x.name||"")+(x.likelihood!=null?
              ' <span class="dim">'+pct(x.likelihood)+"</span>":"");
          }).join(", ")
        : '<span class="dim">no data &mdash; written by the weekly opponent agents once the season starts</span>')+'</p>');
    if(t.blocking_opportunity && !/^none$/i.test(t.blocking_opportunity))
      cc.insertAdjacentHTML("beforeend",'<p class="small"><span class="badge b-amb">BLOCK</span> '+
        md(t.blocking_opportunity)+'</p>');
    cc.insertAdjacentHTML("beforeend",'<p class="small"><b>Exploitable weakness</b><br>'+
      (t.exploitable_weakness ? md(t.exploitable_weakness)
        : (hole ? md(hole)+' <span class="dim">(draft-day read, not an in-season model)</span>'
                : '<span class="dim">no data yet</span>'))+'</p>');
    if(t.trade_appetite) cc.insertAdjacentHTML("beforeend",
      '<p class="small"><b>Trade appetite</b><br>'+md(t.trade_appetite)+'</p>');

    var det=[];
    if((t.starters||[]).length) det.push('<details><summary>Roster</summary><div class="bd">'+
      table(["Slot","Player","Pos","Team"],(t.starters||[]).map(function(p){
        return [p.slot,p.name,p.pos,p.team||""];}))+
      ((t.bench||[]).length?'<h3>Bench</h3>'+table(["Player","Pos","Team"],
        t.bench.map(function(p){return [p.name,p.pos,p.team||""];})):"")+
      '</div></details>');
    if((t.data_gaps||[]).length) det.push('<details><summary>Data gaps ('+
      t.data_gaps.length+')</summary><div class="bd"><ul class="tight">'+
      t.data_gaps.map(function(g){return "<li>"+esc(g)+"</li>";}).join("")+
      '</ul></div></details>');
    cc.insertAdjacentHTML("beforeend", det.join(""));
    f.appendChild(cc);
  });
  return f;
}

/* ---------- TAB: WAIVERS ---------- */
function tabWaivers(){
  var f=document.createDocumentFragment(), w=D.waivers||{};
  var c=card("Waiver system");
  c.insertAdjacentHTML("beforeend",'<div class="kv">'+
    '<div><span>Type</span><b style="font-size:13px">'+
      esc(w.is_faab?"FAAB":"PRIORITY")+'</b></div>'+
    '<div><span>My priority</span><b>'+esc(w.andrew_position==null?"?":w.andrew_position)+'</b></div>'+
    '<div><span>Teams ahead</span><b>'+((w.teams_ahead||[]).length)+'</b></div>'+
    '<div><span>Add keeper cost</span><b>R'+esc(w.keeper_add_cost_round||12)+'</b></div>'+
    '</div>');
  if(w.priority_rule) c.insertAdjacentHTML("beforeend",'<p class="small mut">'+esc(w.priority_rule)+'</p>');
  if(w.type_evidence) c.insertAdjacentHTML("beforeend",
    '<p class="dim small">Evidence: '+esc(w.type_evidence)+'</p>');
  if(!w.day_verified) c.insertAdjacentHTML("beforeend",
    '<div class="warnbox"><b>processing day unconfirmed</b>'+
    esc(w.deadline_guidance||"")+(w.day_note?"<br><br>"+esc(w.day_note):"")+'</div>');
  f.appendChild(c);

  var cs=card("Claim sheet");
  if(w.has_claim_sheet){
    var faab = (w.claims||[]).some(function(x){return x.faab_bid_pct!=null;});
    cs.insertAdjacentHTML("beforeend", table(
      ["#","Player",faab?"Bid":"P(land)","Drop","2027 keeper","Why"],
      (w.claims||[]).map(function(x,i){return [
        String(x.order||i+1),
        x.player||x.name||"",
        faab ? (x.faab_bid_pct!=null?x.faab_bid_pct+"%":"&mdash;")
             : (x.probability!=null?pct(x.probability):"&mdash;"),
        x.drop||"&mdash;",
        x.keeper_equity_2027||x.keeper_equity||"&mdash;",
        x.note||x.rationale||x.why||""];})));
  } else {
    cs.insertAdjacentHTML("beforeend", nodata("no claim sheet", w.claim_note||""));
  }
  f.appendChild(cs);

  var dc=card("Drop candidates");
  if((w.drops||[]).length){
    dc.insertAdjacentHTML("beforeend", table(["#","Player","What you lose","2027 keeper","Verdict"],
      w.drops.map(function(x,i){return [String(x.rank||i+1),x.player||x.name||"",
        x.what_you_lose||x.cost||"",
        x.keeper_equity_2027||x.keeper_equity||"&mdash;",
        x.verdict||""];})));
  } else {
    dc.insertAdjacentHTML("beforeend", nodata("no drop candidates",
      "Produced alongside the claim sheet. Nothing to drop before a roster exists."));
  }
  f.appendChild(dc);

  var oc=card("Priority order");
  if((w.order||[]).length){
    oc.insertAdjacentHTML("beforeend", table(["#","Owner",""],
      w.order.map(function(r){return [String(r.priority), r.owner||("roster "+r.roster_id),
        r.is_andrew?"**YOU**":""];})));
  } else { oc.insertAdjacentHTML("beforeend", nodata("no order","waiver_order is empty in state.")); }
  f.appendChild(oc);

  var fc=card("Verified free agents",
    '<span class="badge b-gry">'+((w.free_agents||[]).length)+' + '+
    ((w.available_defenses||[]).length)+' DEF</span>');
  if(w.fa_gate) fc.insertAdjacentHTML("beforeend",'<p class="small mut">'+esc(w.fa_gate)+'</p>');
  if((w.free_agents||[]).length){
    fc.insertAdjacentHTML("beforeend", table(["Player","Pos","Team"],
      w.free_agents.map(function(p){return [p.name,p.pos,p.team||""];})));
  } else {
    fc.insertAdjacentHTML("beforeend", nodata("empty","No confirmed free agents in state."));
  }
  if(w.fa_caveat) fc.insertAdjacentHTML("beforeend",
    '<p class="dim small">'+esc(w.fa_caveat)+'</p>');
  if((w.available_defenses||[]).length) fc.insertAdjacentHTML("beforeend",
    '<details><summary>Available defenses ('+w.available_defenses.length+
    ')</summary><div class="bd"><p>'+w.available_defenses.map(function(d){
      return '<span class="badge b-gry" style="margin:2px 3px 2px 0">'+
      esc(d.name||d.team||d)+'</span>';}).join("")+'</p></div></details>');
  f.appendChild(fc);
  return f;
}

/* ---------- TAB: TRADES ---------- */
function tabTrades(){
  var f=document.createDocumentFragment(), t=D.trades||{};
  var c=card("Trade board");
  c.insertAdjacentHTML("beforeend",'<p class="small mut">Deadline: week '+
    esc(t.trade_deadline_week||"?")+
    (t.weeks_to_deadline!=null?' <span class="badge '+
      (t.weeks_to_deadline<=2?"b-red":"b-gry")+'">'+t.weeks_to_deadline+
      ' weeks left</span>':"")+
    ' &middot; phase: '+esc(t.phase||"?")+
    ' &middot; draft-pick trading '+(t.pick_trading_allowed?"ALLOWED":"not allowed")+'</p>');
  if(t.has_offers){
    (t.offers||[]).forEach(function(o){
      var offer = o.offer ||
        ((o.send||[]).join(", ")+" → "+(o.receive||[]).join(", "));
      c.insertAdjacentHTML("beforeend",
        '<div style="border-top:1px solid var(--line);padding:11px 0">'+
        '<div><span class="badge b-blu">'+esc(o.to_owner||o.to||o.owner||"?")+
        '</span></div>'+
        '<p style="margin:7px 0 4px"><b>'+md(offer)+'</b></p>'+
        (o.rationale?'<p class="small mut">'+md(o.rationale)+'</p>':"")+
        (o.message_to_send?'<details><summary>Message to send</summary>'+
          '<div class="bd">'+md(o.message_to_send)+'</div></details>':"")+
        '</div>');
    });
  } else {
    c.insertAdjacentHTML("beforeend", nodata("no offers yet", t.note||""));
  }
  f.appendChild(c);

  var ac=card("Rival trade appetite");
  var rows=(t.appetites||[]).filter(function(a){return a.trade_appetite;});
  if(rows.length){
    ac.insertAdjacentHTML("beforeend", table(["Owner","Appetite","Confidence"],
      rows.map(function(a){return [a.owner||("roster "+a.roster_id),
        a.trade_appetite,a.confidence||""];})));
  } else {
    ac.insertAdjacentHTML("beforeend", nodata("no data",
      "Filled from opponent_model.trade_appetite once the weekly run has produced one. "+
      "Until then the OPPONENTS tab shows each rival's draft-day hole, which is the "+
      "only rival-need signal that actually exists right now."));
  }
  f.appendChild(ac);
  return f;
}

/* ---------- TAB: KEEPERS ---------- */
function keeperRows(list){
  return list.map(function(r){
    var cost = r.keeper_cost_2027 || (r.keeper_cost_round?("R"+r.keeper_cost_round):null);
    var yrs = r.consecutive_years_if_kept;
    return [
      r.player+" ("+(r.position||"")+")",
      cost || "unknown",
      r.forfeits_overall_pick?("p"+r.forfeits_overall_pick):"&mdash;",
      (yrs!=null? yrs+" of 3":"?")+(r.is_final_eligible_year?" **FINAL**":""),
      r.eligible===false ? ("**ineligible** &mdash; "+(r.ineligible_reason||"")) : (r.surplus||"unknown")
    ];
  });
}
function tabKeepers(){
  var f=document.createDocumentFragment(), k=D.keepers||{};
  var r=k.rules||{};
  var c=card("Keeper rules");
  c.insertAdjacentHTML("beforeend",'<div class="kv">'+
    '<div><span>Max keepers</span><b>'+esc(r.max_keepers||3)+'</b></div>'+
    '<div><span>Consecutive cap</span><b>'+esc(r.max_consecutive_years||3)+'</b></div>'+
    '<div><span>FA add cost</span><b>R'+esc(r.undrafted_pickup_cost_round||12)+'</b></div>'+
    '<div><span>R1</span><b style="font-size:13px">'+
      (r.first_round_ineligible?"INELIGIBLE":"ok")+'</b></div></div>');
  if(r.cost_rule) c.insertAdjacentHTML("beforeend",'<p class="small mut">'+esc(r.cost_rule)+'</p>');
  c.insertAdjacentHTML("beforeend",'<p class="small"><span class="badge b-pur">THE EDGE</span> '+
    esc(k.waiver_add_note||"")+'</p>');
  f.appendChild(c);

  var c27=card("2027 board &mdash; carried forward",
    '<span class="badge b-grn">'+((k.carried_2027||[]).length)+'</span>');
  if((k.carried_2027||[]).length){
    c27.insertAdjacentHTML("beforeend",'<p class="small mut">These are the three '+
      'players in the 2026 keep plan. Their cost carries forward unchanged and their '+
      'consecutive-year clock advances by one.</p>');
    c27.insertAdjacentHTML("beforeend", table(
      ["Player","2027 cost","Forfeits","Years","Surplus"], keeperRows(k.carried_2027)));
  } else {
    c27.insertAdjacentHTML("beforeend", nodata("no data","No 2026 keeper plan to carry forward."));
  }
  c27.insertAdjacentHTML("beforeend",'<p class="dim small">'+esc(k.projection_note||"")+'</p>');
  f.appendChild(c27);

  if((k.unknown_2027||[]).length){
    var cu=card("2027 cost unknown",
      '<span class="badge b-amb">'+k.unknown_2027.length+'</span>');
    cu.insertAdjacentHTML("beforeend",'<p class="small mut">Not in the 2026 keep plan, '+
      'so they re-enter the draft on Aug 28. Their 2027 keeper cost is the round they '+
      'are drafted in &mdash; it does not exist yet and is deliberately not guessed here.</p>');
    cu.insertAdjacentHTML("beforeend", table(["Player","Pos","2026 cost was"],
      k.unknown_2027.map(function(x){return [x.player,x.position||"",
        (D.keepers.board_2026||[]).filter(function(y){
          return y.player_id===x.player_id;}).map(function(y){
            return y.keeper_cost_2027||"";})[0]||"&mdash;"];})));
    f.appendChild(cu);
  }

  var c26=card("2026 decision board (this August)");
  if((k.board_2026||[]).length){
    c26.insertAdjacentHTML("beforeend", table(
      ["Player","2026 cost","Forfeits","Years","Surplus"], keeperRows(k.board_2026)));
  } else {
    c26.insertAdjacentHTML("beforeend", nodata("no data","keeper_equity produced nothing."));
  }
  f.appendChild(c26);

  var cw=card("In-season keeper watchlist");
  if((k.state_keeper_equity||[]).length){
    cw.insertAdjacentHTML("beforeend", table(["Player","Where","2027 cost","Projected","Surplus"],
      k.state_keeper_equity.map(function(x){return [x.player||"",x.acquired||"",
        x.keeper_cost_2027||"&mdash;",x.projected_value||"&mdash;",
        (x.surplus||"")+(x.note?" — "+x.note:"")];})));
  } else {
    cw.insertAdjacentHTML("beforeend", nodata("empty",
      "state.keeper_equity accumulates every in-season waiver add and its 2027 value at "+
      "a 12th-round price. It fills up as the season runs; there is nothing in it before "+
      "the draft."));
  }
  f.appendChild(cw);
  return f;
}

/* ---------- TAB: STATUS ---------- */
function tabStatus(){
  var f=document.createDocumentFragment(), b=D.build||{};
  var c=card("Data provenance");
  c.insertAdjacentHTML("beforeend", table(["Field","Value"],[
    ["State file", b.state_file||"none"],
    ["State generated", b.state_generated_at||"unknown"],
    ["Dashboard built", b.generated_at||""],
    ["Week", String(b.week)],
    ["League status", b.league_status||""],
    ["Degraded", b.degraded?"**YES**":"no"]
  ],{raw:false}));
  f.appendChild(c);

  var s=b.sources||{};
  if(s.loaded||s.missing){
    var sc=card("Sources");
    sc.insertAdjacentHTML("beforeend",'<p class="small"><b>Loaded:</b> '+
      esc((s.loaded||[]).join(", ")||"none")+'</p>');
    if((s.missing||[]).length) sc.insertAdjacentHTML("beforeend",
      '<p class="small"><b>Missing:</b> <span style="color:var(--amb)">'+
      esc(s.missing.join(", "))+'</span></p>');
    if((s.unparseable||[]).length) sc.insertAdjacentHTML("beforeend",
      '<p class="small"><b>Unparseable:</b> <span style="color:var(--red)">'+
      esc(s.unparseable.join(", "))+'</span></p>');
    var pcx=s.players_cache;
    if(pcx) sc.insertAdjacentHTML("beforeend",'<div class="kv">'+
      '<div><span>Player ids</span><b>'+esc(pcx.total_ids)+'</b></div>'+
      '<div><span>Named</span><b>'+esc(pcx.named)+'</b></div>'+
      '<div><span>Unresolved</span><b>'+esc(pcx.unresolved)+'</b></div>'+
      '<div><span>Stale</span><b>'+esc(pcx.stale_rostered)+'</b></div></div>');
    f.appendChild(sc);
  }
  if((b.state_warnings||[]).length){
    var wc=card("State warnings");
    wc.insertAdjacentHTML("beforeend",'<ul class="tight">'+
      b.state_warnings.map(function(x){return "<li>"+esc(x)+"</li>";}).join("")+'</ul>');
    f.appendChild(wc);
  }
  if((b.build_warnings||[]).length){
    var bw=card("Dashboard build warnings");
    bw.insertAdjacentHTML("beforeend",'<ul class="tight">'+
      b.build_warnings.map(function(x){return "<li>"+esc(x)+"</li>";}).join("")+'</ul>');
    f.appendChild(bw);
  }
  if((b.open_questions||[]).length){
    var oq=card("Open questions");
    oq.insertAdjacentHTML("beforeend",'<ul class="tight">'+
      b.open_questions.map(function(x){
        return "<li>"+esc(typeof x==="string"?x:(x.question||JSON.stringify(x)))+"</li>";
      }).join("")+'</ul>');
    f.appendChild(oq);
  }
  if((D.standings||[]).length){
    var st=card("Standings");
    st.insertAdjacentHTML("beforeend", table(["#","Team","Rec","PF","Wvr"],
      D.standings.map(function(r){return [String(r.rank),
        (r.is_andrew?"**":"")+(r.team_name||r.owner)+(r.is_andrew?"**":""),
        r.wins+"-"+r.losses, String(r.pf), String(r.waiver_priority)];})));
    f.appendChild(st);
  }
  var rc=card("Weekly report");
  if(D.report){
    rc.insertAdjacentHTML("beforeend",'<div class="bd small" style="white-space:pre-wrap">'+
      esc(D.report)+'</div>');
  } else {
    rc.insertAdjacentHTML("beforeend", nodata("no report",
      "No file at "+(b.report_path||"system/reports/week_N.md")+
      ". Written by the weekly.js synthesis step."));
  }
  f.appendChild(rc);
  return f;
}

/* ---------- tab wiring ---------- */
var TABS=[
  {id:"draft",   label:"DRAFT",     build:tabDraft,
   pill:function(){var d=D.draft||{};return d.days_until!=null?(Math.ceil(d.days_until)+"d"):null;}},
  {id:"myteam",  label:"MY TEAM",   build:tabMyTeam,
   pill:function(){var t=D.my_team||{};return (t.injuries||[]).length?String(t.injuries.length)+"!":null;}},
  {id:"opp",     label:"OPPONENTS", build:tabOpponents,
   pill:function(){return String(((D.opponents||{}).cards||[]).length);}},
  {id:"waivers", label:"WAIVERS",   build:tabWaivers,
   pill:function(){var w=D.waivers||{};return w.andrew_position!=null?("#"+w.andrew_position):null;}},
  {id:"trades",  label:"TRADES",    build:tabTrades,
   pill:function(){var t=D.trades||{};return t.has_offers?String((t.offers||[]).length):null;}},
  {id:"keepers", label:"KEEPERS",   build:tabKeepers,
   pill:function(){return String(((D.keepers||{}).carried_2027||[]).length);}},
  {id:"status",  label:"STATUS",    build:tabStatus,
   pill:function(){var b=D.build||{};var n=(b.build_warnings||[]).length+(b.state_warnings||[]).length;
     return n?String(n):null;}}
];
var main=document.getElementById("main"), tabsEl=document.getElementById("tabs");
var built={};
function show(id){
  TABS.forEach(function(t){
    var btn=document.getElementById("tb-"+t.id);
    var pan=document.getElementById("pn-"+t.id);
    var on = t.id===id;
    btn.setAttribute("aria-selected", on?"true":"false");
    pan.classList.toggle("on", on);
    if(on && !built[t.id]){
      try{ pan.appendChild(t.build()); }
      catch(e){ pan.innerHTML='<div class="card"><div class="nodata"><b>render error</b>'+
        esc(t.label+": "+e.message)+'</div></div>'; }
      built[t.id]=true;
    }
  });
  if(location.hash.slice(1)!==id){ try{ history.replaceState(null,"","#"+id); }catch(e){} }
  window.scrollTo(0,0);
  /* the tab strip scrolls horizontally on a phone (7 tabs need ~920px at 390px wide).
     Without this the active tab can sit entirely off-screen -- e.g. opening
     dashboard.html#status shows three unselected tabs and no indication of where
     you are. Centre the selected tab inside the strip; never move the page. */
  try{
    var ab=document.getElementById("tb-"+id);
    if(ab && tabsEl && tabsEl.scrollWidth > tabsEl.clientWidth+1){
      var br=ab.getBoundingClientRect(), sr=tabsEl.getBoundingClientRect();
      var delta=(br.left-sr.left)-(sr.width-br.width)/2;
      var want=Math.max(0,Math.min(tabsEl.scrollLeft+delta,
                                   tabsEl.scrollWidth-tabsEl.clientWidth));
      tabsEl.scrollLeft=want;
    }
  }catch(e){}
}
TABS.forEach(function(t){
  var b=el("button","tab");
  b.id="tb-"+t.id; b.type="button"; b.setAttribute("role","tab");
  b.setAttribute("aria-controls","pn-"+t.id); b.setAttribute("aria-selected","false");
  var p=null; try{ p=t.pill(); }catch(e){}
  b.innerHTML=esc(t.label)+(p?' <span class="pill">'+esc(p)+"</span>":"");
  b.addEventListener("click",function(){show(t.id);});
  tabsEl.appendChild(b);
  var s=el("section"); s.id="pn-"+t.id; s.setAttribute("role","tabpanel");
  s.setAttribute("aria-labelledby","tb-"+t.id);
  main.appendChild(s);
});
var start=(location.hash||"").slice(1);
show(TABS.some(function(t){return t.id===start;})?start:"draft");
window.addEventListener("hashchange",function(){
  var h=location.hash.slice(1);
  if(TABS.some(function(t){return t.id===h;})) show(h);
});
document.getElementById("foot").innerHTML =
  "Sunday Scaries dashboard &middot; self-contained, no network calls &middot; "+
  "regenerate with <code>python3 system/ui/build_dashboard.py</code><br>"+
  "Every panel marked NO DATA is genuinely empty upstream, not a placeholder for "+
  "content that exists elsewhere.";
</script>
</body>
</html>
"""


def render(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # A </script> inside JSON would terminate the tag early; </ is the only
    # sequence that matters inside an application/json script block.
    payload = payload.replace("</", "<\\/")
    return TEMPLATE.replace("%%DATA%%", payload)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the Sunday Scaries dashboard.")
    ap.add_argument("--week", type=int, default=None,
                    help="week number of the state file (default: highest found)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output HTML path")
    ap.add_argument("--synthesis", default=None,
                    help="path to the FULL synthesis agent object (action card, "
                         "claim sheet, trade board). Defaults to "
                         "state/week_N.synthesis.json if present.")
    ap.add_argument("--print-data", action="store_true",
                    help="print the JSON payload instead of writing HTML")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    data = collect(args.week, args.synthesis)
    if args.print_data:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    htmltext = render(data)
    outdir = os.path.dirname(os.path.abspath(args.out))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(htmltext)

    if not args.quiet:
        b = data["build"]
        print("dashboard -> %s (%d bytes)" % (args.out, len(htmltext)))
        print("  state    : %s" % (b["state_file"] or "NONE"))
        print("  week     : %s   phase: %s   status: %s" % (
            b["week"], (b["season_phase"] or {}).get("name"), b["league_status"]))
        print("  data as of %s" % b["state_generated_at"])
        d = data["draft"]
        print("  draft    : slot %s, %d live picks, %d forfeited, %d dead zones" % (
            d.get("slot"), len(d.get("live_overalls") or []),
            len(d.get("forfeited") or []),
            len([g for g in d.get("gaps") or [] if g.get("dead_zone")])))
        print("  board    : %s" % ("parsed from draft_board_2026.md"
                                   if (d.get("board") or {}).get("available")
                                   else "PLACEHOLDER (draft_board_2026.md missing)"))
        print("  opponents: %d cards, model=%s pressure=%s" % (
            len(data["opponents"]["cards"]), data["opponents"]["has_model"],
            data["opponents"]["has_pressure"]))
        print("  synthesis: %s -> action_card=%d claims=%d trades=%d" % (
            b.get("synthesis_file") or "none", len(data["action_card"]),
            len(data["waivers"]["claims"]), len(data["trades"]["offers"])))
        for w in b["build_warnings"]:
            print("  WARN: %s" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
