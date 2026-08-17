# Where the files live, and how to keep them

Short answer: **no, you can't browse the source directory from another computer.** Here's the accurate picture and what to do about it.

---

## The three places files can be

**1. This session's cloud container — where I've been working.**
Everything lives at `/home/claude/sunday_scaries/` — 53 files, about 2 MB. This is a private Linux sandbox in Anthropic's cloud, not a shared drive. You can't mount it, browse it, or SSH into it, and **it gets reclaimed after a period of inactivity or when the session ends.** Nothing here is permanent.

**2. This conversation — where the durable copies are.**
Every file I've sent you is attached to this chat and downloadable from any device where you can open this conversation: phone, desktop, web. That is the real persistence layer. If you can open this chat, you can get the files.

**3. Your own computer — not currently reachable.**
There's a bridge that lets me read and write files on your machine directly, but it only works while the Claude **desktop app** is open and connected. I checked — it isn't available right now. If you open the desktop app and come back, I can write the whole directory straight into a folder on your computer.

---

## Do this now: grab the archive

I've bundled the entire working directory into `sunday_scaries_COMPLETE.tar.gz` (673 KB). One file, everything in it. Save it somewhere you control — email it to yourself, drop it in cloud storage, whatever you'll actually be able to find in November.

To open it on your own machine:

```bash
tar -xzf sunday_scaries_COMPLETE.tar.gz
```

On Mac, double-clicking works too. On Windows, use 7-Zip or WinRAR.

---

## What's inside

**Draft prep**
- `draft_board_2026.md` — the slot-8 board: supply/demand model, tier tables, pick-by-pick targets, three mock drafts, Mermaid decision trees
- `league_reference.md` — league constants, keeper-cost board for all 10 teams, pick map, live trackers
- `news_sweep_full_report.md` — all 32 NFL teams, your roster, rival keepers, league-wide trends
- `draft_research_interim.md` — raw positional research behind the board
- `keeper_cost_board.txt` — every player on every roster with their keeper cost

**The in-season system** (`system/`)
- `league_config.json`, `players_cache.json` — constants and all 222 resolved players
- `state_builder.py`, `players_cache.py`, `merge_state.py` — the deterministic data layer
- `analysis/` — opponent pressure, waiver contention, keeper equity, exact scoring, plus tests
- `weekly.js` — the 18-agent weekly workflow
- `skill/` — the skill source, and `ui/dashboard.html`
- `state/week_0.json` — a real preseason baseline
- `raw/` — live-fetched league data and all 160 of last year's draft picks

**The skill, packaged**
- `sunday-scaries.skill` — the installable bundle (also sent separately)
- `SKILL_README.md` — what it is and how to use it

**Process docs**
- `weekly_system_plan.md` — the architecture design
- `IMPLEMENTATION_LOG.md` — what got built, run IDs for resuming
- `gap_fill_plan.md` — the audit that caught the incomplete research

---

## Recommended: keep two things

1. **`sunday-scaries.skill`** — if a save option appeared when I sent it, that's your one-command path. Everything needed to rebuild is bundled inside it.
2. **`sunday_scaries_COMPLETE.tar.gz`** — the full archive, including drafts, research, and process history that isn't in the skill.

With either one, a brand-new chat months from now can pick this up cold. Attach the file and say "unzip this and read SKILL.md" — the system is designed so the files are canonical and the chat is disposable.
