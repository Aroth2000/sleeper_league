#!/usr/bin/env python3
"""
merge_state.py -- fold the synthesis agent's model-derived sections back into the
deterministic state file, without letting a model overwrite a fact.

WHY THIS EXISTS
---------------
Two things both wanted to own system/state/week_N.json:

  1. state_builder.py, which computes standings, rosters, starters, matchups,
     transactions, injuries and the verified free-agent set straight from the
     Sleeper payloads. Nothing here can be hallucinated.
  2. weekly.js's synthesis agent, which produces opponent_model, keeper_equity,
     decisions_log and open_questions -- judgment, not fact.

Before this script existed, the documented order of operations was "run
state_builder, then run the workflow, then write state_json to week_N.json",
which meant the deterministic file was silently destroyed by an LLM's
reconstruction of it every single week -- and next week read that reconstruction
as ground truth. The plan is explicit that the hard facts belong in code, not a
prompt (Part 3 Phase 0, Part 7). This script enforces that split.

MECHANICS
---------
  deterministic  = state/week_N.json          (state_builder.py, authoritative)
  synthesis      = state/week_N.synthesis.json (weekly.js, model-derived)
  output         = state/week_N.json          (merged; a .prebuild backup is kept)

Only MODEL_SECTIONS are taken from the synthesis file. Every other key is taken
from the deterministic file, unconditionally. If the synthesis file is missing or
unparseable the deterministic file is left exactly as it is and the script exits
non-zero -- a run with no opponent model is worse than a run with a stale one,
but both are far better than a run whose standings were invented.

USAGE
    python3 merge_state.py --week 7
    python3 merge_state.py --deterministic state/week_7.json \
                           --synthesis state/week_7.synthesis.json
    python3 merge_state.py --week 7 --dry-run
"""

import datetime
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")

# The only sections a model is allowed to own. Everything else is derived from
# the Sleeper payloads and is not up for negotiation.
MODEL_SECTIONS = ("opponent_model", "keeper_equity", "decisions_log", "open_questions")

# open_questions is unioned rather than replaced: the builder raises structural
# gaps (empty bye map, unresolved ids) that the agent has no way to know about.
UNION_SECTIONS = ("open_questions",)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _load(path, label):
    if not os.path.exists(path):
        return None, "%s missing: %s" % (label, path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError as exc:
        return None, "%s unreadable: %s" % (label, exc)
    if not text:
        return None, "%s is empty: %s" % (label, path)
    # Tolerate a model wrapping its JSON in a markdown fence.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, "%s is not valid JSON: %s" % (label, exc)


def merge(deterministic, synthesis):
    """Return (merged_dict, notes). `deterministic` wins on every non-model key."""
    out = dict(deterministic)
    notes = []
    taken, skipped = [], []

    for key in MODEL_SECTIONS:
        if key not in synthesis:
            skipped.append(key)
            continue
        value = synthesis[key]
        if value in (None, "", [], {}):
            skipped.append(key + " (empty)")
            continue
        if key in UNION_SECTIONS:
            base = out.get(key) or []
            base = base if isinstance(base, list) else [base]
            extra = value if isinstance(value, list) else [value]
            seen, merged = set(), []
            for item in base + extra:
                k = json.dumps(item, sort_keys=True) if not isinstance(item, str) else item
                if k in seen:
                    continue
                seen.add(k)
                merged.append(item)
            out[key] = merged
        else:
            out[key] = value
        taken.append(key)

    ignored = sorted(k for k in synthesis if k not in MODEL_SECTIONS)
    if ignored:
        notes.append(
            "synthesis also emitted %s -- IGNORED, those come from state_builder.py"
            % ", ".join(ignored))
    if skipped:
        notes.append("synthesis did not supply: " + ", ".join(skipped))
    notes.append("took from synthesis: " + (", ".join(taken) or "(nothing)"))

    meta = dict(out.get("meta") or {})
    meta["merged_at"] = _now()
    meta["merge_sections_from_model"] = taken
    meta["merge_notes"] = notes
    out["meta"] = meta
    return out, notes


def main(argv):
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

    dry = "--dry-run" in argv
    week = arg("--week")
    det = arg("--deterministic")
    syn = arg("--synthesis")
    out_path = arg("--out")

    if week is not None and not det:
        det = os.path.join(STATE_DIR, "week_%s.json" % week)
    if det and not syn:
        syn = det[:-5] + ".synthesis.json" if det.endswith(".json") else det + ".synthesis.json"
    if not det:
        print("usage: merge_state.py --week N  |  --deterministic PATH [--synthesis PATH]",
              file=sys.stderr)
        return 2
    out_path = out_path or det

    d, err = _load(det, "deterministic state")
    if err:
        print("FATAL: " + err, file=sys.stderr)
        print("       Run: python3 state_builder.py --week %s" % (week or "N"), file=sys.stderr)
        return 2

    s, err = _load(syn, "synthesis state")
    if err:
        print("WARNING: " + err, file=sys.stderr)
        print("         Leaving %s untouched. The deterministic facts are intact;" % det,
              file=sys.stderr)
        print("         the opponent model / keeper equity for this week are missing.",
              file=sys.stderr)
        return 1
    if not isinstance(s, dict):
        print("FATAL: synthesis state is not a JSON object", file=sys.stderr)
        return 2

    merged, notes = merge(d, s)

    if dry:
        for n in notes:
            print("  " + n)
        print("(dry run -- nothing written; would write %s)" % out_path)
        return 0

    if os.path.exists(out_path) and out_path == det:
        shutil.copyfile(out_path, out_path[:-5] + ".prebuild.json")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, out_path)

    for n in notes:
        print("  " + n)
    print("wrote %s  (%s bytes)" % (out_path, format(os.path.getsize(out_path), ",")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
