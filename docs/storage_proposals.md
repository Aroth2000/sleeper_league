# Two proposals: where weekly briefs live long-term

Both proposals solve the same two problems: (1) you can find any past week's brief a month from
now without hunting through separate chat sessions, and (2) each Tuesday's run actually reads
last week's real state instead of a stale snapshot, so the "diff, don't snapshot" design works
the way it was meant to.

Neither has been implemented. Pick one (or ask for changes) and I'll wire it into `SKILL.md` and
the scheduled task's prompt.

---

## Proposal A: Google Drive

**What it is.** One shared Drive folder — `Sunday Scaries/2026/` — that every Tuesday's session
reads from and writes to. Nothing lives only inside a chat session anymore; the folder is the
canonical archive.

**What changes in the system:**

- **Setup (one-time, done by you):** connect the Google Drive connector to your account. Takes
  about a minute, standard OAuth, same as connecting Drive to any other app.
- **Folder layout:**
  ```
  Sunday Scaries/2026/
    week_01/  report.md   state.json   dashboard.html
    week_02/  report.md   state.json   dashboard.html
    ...
  ```
- **Step 1 of the weekly run changes:** instead of restoring from the skill's bundled snapshot,
  the session searches the Drive folder for the highest-numbered `week_N/state.json`, reads it,
  and uses that as last week's real ground truth.
- **Step 4 changes:** instead of (or in addition to) sending files into the chat, the session
  writes `report.md`, `state.json`, and the regenerated `dashboard.html` into a new `week_N/`
  folder in Drive.
- **Viewing:** open the Drive app on your phone anytime, browse to any week, done. No searching
  through old chat sessions.

**Pros:**
- Works no matter what device is on or off — Drive is always reachable.
- Solves both problems at once: real archive *and* real week-to-week memory.
- Nothing new to remember to do each week; it's fully automatic once connected.

**Cons / open questions to verify on the first real run:**
- Org-connected tools (like Drive) are sometimes unavailable to a background/scheduled session
  the way they are to an interactive one — this is a documented edge case for headless runs. I'd
  confirm this works on the very first Tuesday firing after setup and have a fallback (deliver to
  chat only, flag Drive as unreachable) ready if it doesn't.
- Adds Google as a dependency — if you ever disconnect Drive, the archive step silently stops
  (the brief itself would still get delivered to chat as a safety net).

---

## Proposal B: Your desktop, via the device bridge

**What it is.** Files get written directly into a real folder on your own computer —
`Documents/Sunday Scaries/2026/week_N/` — using the same bridge that lets me read/write your
local files when the desktop Claude app is open.

**What changes in the system:**

- **Setup:** none — no new account, no OAuth. Uses the bridge you already have.
- **The honest catch:** the bridge only exists while your desktop Claude app is open and
  connected *to that specific session*. The Tuesday scheduled task fires a brand-new cloud
  session on its own — it is not guaranteed to have a live bridge to your desktop at 8am on a
  Tuesday just because the trigger fired. In practice this likely means one of two patterns:
  - **Automatic-when-lucky:** if your desktop app happens to be open at fire time, the write
    succeeds; if your laptop is asleep or closed (the exact scenario you said you wanted this to
    survive), it doesn't, and that week's local copy just doesn't land until you catch it up.
  - **Manual catch-up:** more realistically, the brief still gets delivered to chat every Tuesday
    like today, and separately — whenever you do have the desktop app open, whether that's the
    same day or a week later — you ask me to pull whatever's accumulated in chat and file it into
    the right week folders on your machine. Same folder structure and end result, just not
    triggered automatically by the cron job itself.
- Because of that same gap, this option is weaker at fixing the *second* problem (next week's
  run reading last week's real state) unless your desktop happens to be connected right when the
  next run fires too.

**Pros:**
- Files genuinely live only on your machine — the direct ownership you said you wanted.
- No new account or connector, no third-party dependency.
- Natural home for everything else already sent (the `.tar.gz`, the `.skill` file, the dashboard).

**Cons:**
- Not reliably automatic on the actual Tuesday-morning schedule — the one thing you specifically
  wanted this system to do without you lifting a finger.
- Doesn't fully solve the state-continuity problem unless the bridge happens to be live on both
  ends of the gap.
- Realistically becomes a semi-manual "sync when I remember to open the app" workflow rather than
  true unattended automation.

---

## Straight comparison

| | Google Drive | Desktop bridge |
|---|---|---|
| Findable a month from now | Yes, one folder, any device | Yes, but only for weeks that actually synced |
| Works even if your computer is off/asleep Tuesday 8am | Yes | No |
| Fixes week-to-week memory automatically | Yes | Only if bridge happens to be live both weeks |
| New account/connection required | Yes (Google Drive OAuth) | No |
| Files live only on hardware you own | No (Google's servers) | Yes |
| Effort to set up | ~1 minute, once | None |
| Ongoing effort from you | None | Periodic manual catch-up likely |

**My honest read:** Drive is the more architecturally sound fix for what you originally asked
for — a system that runs itself every Tuesday and that you can trust to remember last week. The
desktop option better matches the "I want to be in charge of my own files" instinct you raised
earlier, but at the cost of the automation actually being automatic. You could also do both —
Drive as the automatic source of truth, desktop as a manual periodic backup — if you want the
belt-and-suspenders version.
