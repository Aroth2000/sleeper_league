#!/usr/bin/env python3
"""
repo_sync.py -- give the weekly loop a durable place to read from and write to,
instead of relying on session continuity that does not exist between Tuesday
cloud-scheduled firings.

WHY THIS EXISTS
---------------
Every Tuesday firing starts a brand-new, unrelated session with no access to
what last week's session wrote. The bundled skill snapshot goes stale the
moment one real week passes. This script makes the git repo
(github.com/Aroth2000/sleeper_league) the actual memory: pull it before the
run, read last week's state.json out of it for the diff, and push this week's
outputs into it after the run. "Diff, don't snapshot" only works if there is
somewhere durable to diff against -- this is that somewhere.

SUBCOMMANDS
-----------
  pull
      Clone the repo into --dir (default system/../repo_clone/) if it is not
      there yet, else fetch + fast-forward pull. Never crashes silently on
      failure -- prints a clear warning to stderr and exits non-zero so the
      caller (SKILL.md Step 0) can detect it and fall back to the bundled
      snapshot.

  latest-week
      Look at <dir>/data/week_NN/ subdirectories that actually contain a
      state.json, print the highest NN as a bare integer (e.g. "7"), or the
      literal string "none" if the clone has no week data yet (a fresh repo,
      or the repo has only the week_00 preseason baseline and you asked
      before any real week landed -- week_00 counts and will print "0").

  get-state --week N [--dir DIR] [--out PATH]
      Copy <dir>/data/week_NN/state.json to a local path so
      state_builder.py's diff logic can read it as "last week's real state"
      instead of a possibly-stale bundled copy. Default --out is
      system/state/week_N.json -- the same path weekly.js already defaults
      `prevstate` to, so no other caller needs to change to pick this up.

  commit-and-push --week N --report PATH --state PATH --synthesis PATH
                   [--dir DIR] [--summary TEXT]
      Stage the three files into <dir>/data/week_NN/{report.md,state.json,
      state.synthesis.json}, commit locally, and push. Auth comes ONLY from
      the SUNDAY_SCARIES_GH_TOKEN environment variable -- never hardcoded,
      never written to the git remote config (the token is passed inline on
      the one push invocation's URL, so it never lands in `git remote -v` or
      .git/config). If the env var is unset, this is not an error: it is the
      expected state until a token exists. The commit still happens locally,
      the exact push command is printed, and the process exits 0.

Idempotency: re-running commit-and-push for the same week with identical
file contents is a no-op commit (git has nothing to stage) and the script
still (re)attempts the push, which is itself a safe no-op if the remote
already has that commit. No double-commits, no crash.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
DEFAULT_DIR = os.path.join(PROJECT_ROOT, "repo_clone")
DEFAULT_STATE_DIR = os.path.join(HERE, "state")
REPO_URL = "https://github.com/Aroth2000/sleeper_league.git"
TOKEN_ENV_VAR = "SUNDAY_SCARIES_GH_TOKEN"


def _run(cmd, cwd=None, check=True, capture=True, env=None):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        env=env,
    )
    if check and result.returncode != 0:
        out = (result.stdout or "") + (result.stderr or "")
        raise RuntimeError("command failed (%d): %s\n%s" % (result.returncode, " ".join(cmd), out.strip()))
    return result


def _week_dirname(week):
    """week_00, week_07, week_13, ... -- matches the convention the repo
    bootstrap already committed (data/week_00/state.json)."""
    try:
        n = int(week)
    except (TypeError, ValueError):
        raise ValueError("week must be an integer, got %r" % (week,))
    return "week_%02d" % n


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

def cmd_pull(args):
    target = os.path.abspath(args.dir)
    try:
        if os.path.isdir(os.path.join(target, ".git")):
            print("repo_sync: existing clone found at %s, pulling..." % target)
            _run(["git", "fetch", "origin"], cwd=target)
            # Find the default branch on the remote, fall back to main.
            branch_result = _run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=target, check=False
            )
            branch = (branch_result.stdout or "").strip() or "main"
            pull_result = _run(
                ["git", "pull", "--ff-only", "origin", branch], cwd=target, check=False
            )
            if pull_result.returncode != 0:
                msg = ((pull_result.stdout or "") + (pull_result.stderr or "")).strip()
                last_line = msg.splitlines()[-1] if msg else "(no output)"
                # The ONE genuinely non-fatal case, verified against this
                # project's real state: the remote has no commits on this
                # branch yet (empty upstream -- nothing has been pushed
                # since loop:bootstrap has no push token). git's message for
                # that is "couldn't find remote ref <branch>". There is
                # nothing newer upstream to be behind, so the existing local
                # clone genuinely IS current and it is correct to return 0.
                # Any OTHER ff-pull failure (diverged history, network drop
                # mid-pull, auth/permission change, force-pushed remote) means
                # the clone may be stale, so it must propagate as a non-zero
                # exit -- SKILL.md Step 0 branches on this exit code to decide
                # whether to fall back to the bundled snapshot, and silently
                # returning 0 here would make it wrongly report the clone as
                # current. See LOOP_VERIFICATION_REPORT.md for how this was
                # caught: cmd_pull used to return 0 unconditionally.
                if "couldn't find remote ref" in msg.lower():
                    print(
                        "repo_sync pull: remote has no commits on '%s' yet (empty "
                        "upstream -- expected until this repo has been pushed to). "
                        "The existing local clone has nothing to be behind; "
                        "treating it as current." % branch,
                        file=sys.stderr,
                    )
                else:
                    print(
                        "WARNING: repo_sync pull: fast-forward pull failed (%s). "
                        "The existing local clone may NOT be current -- treating "
                        "this as a failed sync." % last_line,
                        file=sys.stderr,
                    )
                    return 1
        else:
            if os.path.isdir(target) and os.listdir(target):
                print(
                    "WARNING: repo_sync pull: %s exists and is not a git repo "
                    "and is not empty. Refusing to clone over it." % target,
                    file=sys.stderr,
                )
                return 1
            print("repo_sync: no clone yet, cloning %s into %s..." % (REPO_URL, target))
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            _run(["git", "clone", REPO_URL, target])
    except (RuntimeError, OSError) as exc:
        print("WARNING: repo_sync pull FAILED: %s" % exc, file=sys.stderr)
        print(
            "WARNING: falling back to the skill's bundled snapshot is required here -- "
            "the repo clone at %s is not usable." % target,
            file=sys.stderr,
        )
        return 1

    print("repo_sync: pull OK, clone is at %s" % target)
    return 0


# ---------------------------------------------------------------------------
# latest-week
# ---------------------------------------------------------------------------

def _find_weeks(repo_dir):
    data_dir = os.path.join(repo_dir, "data")
    weeks = []
    if not os.path.isdir(data_dir):
        return weeks
    for name in os.listdir(data_dir):
        if not name.startswith("week_"):
            continue
        state_path = os.path.join(data_dir, name, "state.json")
        if not os.path.isfile(state_path):
            continue
        suffix = name[len("week_"):]
        try:
            weeks.append(int(suffix))
        except ValueError:
            continue
    return sorted(weeks)


def cmd_latest_week(args):
    target = os.path.abspath(args.dir)
    if not os.path.isdir(os.path.join(target, ".git")):
        print(
            "WARNING: repo_sync latest-week: %s is not a git clone (run "
            "'repo_sync.py pull' first)." % target,
            file=sys.stderr,
        )
        print("none")
        return 1
    weeks = _find_weeks(target)
    if not weeks:
        print("none")
        return 0
    print(str(weeks[-1]))
    return 0


# ---------------------------------------------------------------------------
# get-state
# ---------------------------------------------------------------------------

def cmd_get_state(args):
    target = os.path.abspath(args.dir)
    week_dirname = _week_dirname(args.week)
    src = os.path.join(target, "data", week_dirname, "state.json")
    out = args.out or os.path.join(DEFAULT_STATE_DIR, "week_%s.json" % int(args.week))

    if not os.path.isfile(src):
        print(
            "WARNING: repo_sync get-state: no %s in the clone (%s). "
            "This is expected for a fresh start with no prior week -- the "
            "caller should proceed with no diff." % (src, target),
            file=sys.stderr,
        )
        return 1

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    shutil.copyfile(src, out)
    print("repo_sync: copied %s -> %s" % (src, out))
    return 0


# ---------------------------------------------------------------------------
# commit-and-push
# ---------------------------------------------------------------------------

def _one_line_summary(report_path, fallback):
    if report_path and os.path.isfile(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip().lstrip("#").strip()
                    if line:
                        return line[:80]
        except OSError:
            pass
    return fallback


def _push_url_with_token(token):
    # Inline basic-auth-style URL. Passed only as a one-off push argument,
    # never written to .git/config or `git remote`, so it never lingers
    # anywhere `git remote -v`, `.git/config`, or shell history-independent
    # inspection would show it.
    return "https://%s@github.com/Aroth2000/sleeper_league.git" % token


def cmd_commit_and_push(args):
    target = os.path.abspath(args.dir)
    if not os.path.isdir(os.path.join(target, ".git")):
        print(
            "WARNING: repo_sync commit-and-push: %s is not a git clone. "
            "Run 'repo_sync.py pull' first." % target,
            file=sys.stderr,
        )
        return 1

    week_dirname = _week_dirname(args.week)
    week_dir = os.path.join(target, "data", week_dirname)
    os.makedirs(week_dir, exist_ok=True)

    copies = [
        (args.report, os.path.join(week_dir, "report.md")),
        (args.state, os.path.join(week_dir, "state.json")),
        (args.synthesis, os.path.join(week_dir, "state.synthesis.json")),
    ]
    missing = [src for src, _ in copies if src and not os.path.isfile(src)]
    if missing:
        print(
            "WARNING: repo_sync commit-and-push: source file(s) not found: %s"
            % ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    for src, dst in copies:
        if src:
            shutil.copyfile(src, dst)
            print("repo_sync: staged %s -> %s" % (src, dst))

    _run(["git", "add", "data/%s" % week_dirname], cwd=target)

    staged = _run(["git", "diff", "--cached", "--name-only"], cwd=target)
    nothing_to_commit = not staged.stdout.strip()

    summary = args.summary or _one_line_summary(args.report, "state + report archived")
    commit_msg = "week %s: %s" % (args.week, summary)

    if nothing_to_commit:
        print(
            "repo_sync: nothing changed for %s (content identical to last commit) "
            "-- skipping commit, this run is idempotent." % week_dirname
        )
    else:
        _run(["git", "commit", "-m", commit_msg], cwd=target)
        print("repo_sync: committed locally: %s" % commit_msg)

    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    branch_result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=target, check=False)
    branch = (branch_result.stdout or "").strip() or "main"

    if not token:
        print(
            "repo_sync: %s is not set -- this is expected until a token exists. "
            "Skipping push. Local commit is safe on disk at %s." % (TOKEN_ENV_VAR, target)
        )
        print(
            "repo_sync: once a token exists, push manually with:\n"
            "    cd %s && git push origin %s\n"
            "  or non-interactively:\n"
            "    cd %s && git push https://<TOKEN>@github.com/Aroth2000/sleeper_league.git %s"
            % (target, branch, target, branch)
        )
        return 0

    push_url = _push_url_with_token(token)
    push_result = _run(["git", "push", push_url, branch], cwd=target, check=False)
    if push_result.returncode != 0:
        out = (push_result.stdout or "") + (push_result.stderr or "")
        print(
            "WARNING: repo_sync commit-and-push: push FAILED (auth or network). "
            "The commit is still safe locally at %s. Details:\n%s"
            % (target, out.strip()),
            file=sys.stderr,
        )
        print(
            "repo_sync: retry manually once the token/network issue is fixed with:\n"
            "    cd %s && git push origin %s" % (target, branch)
        )
        return 1

    print("repo_sync: pushed %s to origin/%s" % (week_dirname, branch))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="repo_sync.py",
        description="Give the weekly loop a durable git-backed memory between Tuesday sessions.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("pull", help="clone or pull the repo into --dir")
    pp.add_argument("--dir", default=DEFAULT_DIR)
    pp.set_defaults(func=cmd_pull)

    lp = sub.add_parser("latest-week", help='highest week_NN with a state.json, or "none"')
    lp.add_argument("--dir", default=DEFAULT_DIR)
    lp.set_defaults(func=cmd_latest_week)

    gp = sub.add_parser("get-state", help="copy data/week_NN/state.json out of the clone")
    gp.add_argument("--week", required=True)
    gp.add_argument("--dir", default=DEFAULT_DIR)
    gp.add_argument("--out", default=None)
    gp.set_defaults(func=cmd_get_state)

    cp = sub.add_parser("commit-and-push", help="stage, commit, and push a week's outputs")
    cp.add_argument("--week", required=True)
    cp.add_argument("--report", default=None)
    cp.add_argument("--state", default=None)
    cp.add_argument("--synthesis", default=None)
    cp.add_argument("--summary", default=None)
    cp.add_argument("--dir", default=DEFAULT_DIR)
    cp.set_defaults(func=cmd_commit_and_push)

    return p


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
