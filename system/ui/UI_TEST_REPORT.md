# Dashboard UI — browser test report

**Tested:** `/home/claude/sunday_scaries/system/ui/dashboard.html` (148,795 bytes after fixes)
**How:** real Chromium via Playwright, `file://` URL, no network.
**Harness:** `/home/claude/sunday_scaries/system/ui/ui_test_playwright.py` — re-runnable, exit 0 = pass.
**Result:** **61 / 61 checks pass** after two fixes applied to `dashboard.html`.

```
cd /home/claude/sunday_scaries/system/ui && python3 ui_test_playwright.py
```

---

## Verdict

**It works, and it is genuinely good on a phone.** This is not a shell full of
placeholders — it is real league data, laid out legibly at 390px, with no
horizontal overflow anywhere, no JavaScript errors, and tab switching that
actually switches. I would hand this to Andrew.

Two real defects were found and fixed. One significant draft-night usability
problem was found and is **not** fixed (it is a design change, not a bug — see
§5). One caveat about fix durability is in §6 and matters more than anything
else in this document.

---

## 1. Load and render

| Check | Result |
|---|---|
| Loads from `file://` at 390×844 | pass |
| Loads at 1440×900 | pass |
| 7 tab buttons present | pass |
| Body text volume | 21,432 chars — real content, not a stub |
| Uncaught page errors | **none** |
| Console errors | **none** |
| Failed subresource requests | **none** |
| Self-contained after my edits | re-verified: 0 hits for `localStorage`, `sessionStorage`, `<link>`, `<img>`, `src=`, `http://`, `https://`, `@import`, `fetch(`, `XMLHttpRequest`, `<iframe>`; 2 script tags / 2 closers; payload JSON re-parses |

Screenshots:
- `screenshot_mobile.png` — 390×844, DRAFT tab
- `screenshot_desktop.png` — 1440×900, DRAFT tab
- `screenshot_tab_myteam.png`, `screenshot_tab_waivers.png` — proof of switching

---

## 2. Tab switching

All 7 tabs clicked in turn at 390px. For each: the target panel's computed
`display` became `block` with non-zero height, **all six others were confirmed
`display:none`**, `aria-selected="true"` moved correctly, and no panel hit the
`render error` fallback.

| Tab | Panel text after click | Verdict |
|---|---|---|
| DRAFT | 28,673 chars | renders |
| MY TEAM | 1,172 chars | renders (10 starters + 7 bench + injuries + bye no-data) |
| OPPONENTS | 12,910 chars | renders (9 rival cards) |
| WAIVERS | 3,030 chars | renders |
| TRADES | 771 chars | renders — legitimately mostly NO DATA pre-season |
| KEEPERS | 2,055 chars | renders |
| STATUS | 2,092 chars | renders |

Deep links (`#draft` … `#status`) all open the right tab on both desktop and
mobile, with no page scroll jump.

---

## 3. Horizontal overflow at 390px — clean

This needed care, because `body{overflow-x:hidden}` **hides the symptom** from
the naive `document.body.scrollWidth > window.innerWidth` test. That check
passes trivially here and proves nothing. So the harness instead walks the DOM
and flags any element whose bounding rect extends past the viewport, plus any
element whose content is being clipped by its own `overflow:hidden`.

**Zero offenders on all 7 tabs.** Also re-tested with **every `<details>` drawer
force-opened** (17 on DRAFT, 18 on OPPONENTS, 1 on WAIVERS — 36 total), because
collapsed drawers hide their content from layout and are the usual place this
bug lives. Still zero. Also clean at **360px and 320px** (iPhone SE), which the
builder never claimed.

The `≤700px` responsive table collapse genuinely works — the wide tables
(injuries, pick targets, tiers, standings) stack into blocks rather than
scrolling sideways.

The only horizontally-scrolling region is `.tabs` (`scrollWidth` 922 vs
`clientWidth` 390) — that is the intended tab strip, not a bug, and it is now
handled properly (§4, Bug 2).

**Tap targets:** every button and `<summary>` measures ≥ 40px tall. Pass.

---

## 4. Bugs found and FIXED in `dashboard.html`

### Bug 1 — active tab could be entirely off-screen on a phone (mobile-only, real)

**Symptom.** Seven tabs need 922px of strip; a 390px phone shows about 2.5 of
them. Opening `dashboard.html#status` on a phone left the tab strip scrolled to
0 while STATUS was the active tab — measured rect **left=796, right=910 in a
390px viewport**, i.e. completely invisible. The user saw three *unselected*
tabs and no indication of which tab they were on. Same for `#keepers` and
`#trades`, and after any `hashchange`.

This is exactly the kind of thing that bites when Andrew bookmarks
`dashboard.html#draft` or taps a link to a specific tab on his phone.

**Fix.** `show()` now centres the selected button inside the strip, using
rect-relative arithmetic so it can never move the page vertically:

```js
var ab=document.getElementById("tb-"+id);
if(ab && tabsEl && tabsEl.scrollWidth > tabsEl.clientWidth+1){
  var br=ab.getBoundingClientRect(), sr=tabsEl.getBoundingClientRect();
  var delta=(br.left-sr.left)-(sr.width-br.width)/2;
  tabsEl.scrollLeft=Math.max(0,Math.min(tabsEl.scrollLeft+delta,
                                        tabsEl.scrollWidth-tabsEl.clientWidth));
}
```

**Verified.** All 7 deep links now land with the active tab fully on-screen and
`window.scrollY === 0`. Seven new regression checks added to the harness.
(`#status` now measures left=264, right=378.)

### Bug 2 — secondary text failed WCAG AA contrast

**Symptom.** `--dim: #6b7a8c` gives **3.95:1** against the card background
`#151b23` and **3.61:1** against nested `--panel2`. AA for normal text is 4.5:1,
and `.dim` is set at **12.5px**, so it is the smallest text on the page. It
carries real content — `"2026-08-28 19:30 ET · 10 teams · 16 rounds · snake"`,
`"positional pressure · confidence low · all zero: no injuries…"`, the
`"no data — written by the weekly opponent agents"` lines. On a phone in a dim
room on draft night this is the text you squint at.

**Fix.** `--dim: #6b7a8c` → `#8090a0`. New ratios: **5.29:1** on `--panel`,
**4.84:1** on `--panel2`, **5.87:1** on the page background — all AA — while
still reading as visibly dimmer than `--mut` (#93a1b1). Nothing else changed.

**Verified.** A live in-browser contrast sweep over every visible
`.dim/.small/.mut/td/.nodata` element now reports a worst case of **5.29** and
is asserted in the harness.

---

## 5. Found, NOT fixed — the DRAFT tab is 28 phone screens long

Measured page height at 390px:

| Tab | Height | Phone screens |
|---|---|---|
| **DRAFT** | **23,691px** | **28.1** |
| WAIVERS | 9,541px | 11.3 |
| KEEPERS | 7,232px | 8.6 |
| OPPONENTS | 5,867px | 7.0 |
| STATUS | 5,613px | 6.7 |
| MY TEAM | 3,101px | 3.7 |
| TRADES | 1,020px | 1.2 |

The DRAFT tab is 14 stacked cards and 23,691 vertical pixels. It reads
beautifully, but the actual use case is: it is 9:15pm on Aug 28, the clock is
running, Andrew is on the clock at pick 68, and he needs the pick-68 row *now*.
Thumb-scrolling through 28 screens to find it is the wrong interaction, and it
is the one moment this whole system exists for.

I did **not** fix this, because it is a design change rather than a defect, it
would be wiped by the next rebuild (§6), and it deserves to be built in the
generator where it can be tested properly.

**Recommendation for whoever owns `build_dashboard.py`:** render a sticky
in-tab chip row from the `<h2>` of each card in the active panel (14 chips on
DRAFT: PICK MAP, 30-SECOND VERSION, PICK TARGETS, TIERS, DEAD ZONES, RULES,
PANIC BUTTONS …), each scrolling to its card. Roughly 15 lines of JS against
markup that already exists. Alternatively, default the reference-material cards
(tiers, scenarios, rules) to collapsed `<details>` and leave only the pick-by-pick
table and the 30-second version expanded.

---

## 6. READ THIS — both fixes live only in the generated file

`dashboard.html` is **generated output**. Both defects originate in
`build_dashboard.py`, which is another agent's file and which I was explicitly
scoped out of:

| Fix | Site in generator |
|---|---|
| Contrast | `build_dashboard.py:977` — `--dim:#6b7a8c` → `--dim:#8090a0` |
| Tab centring | `build_dashboard.py:1918` — insert the block from §4 after `window.scrollTo(0,0);` |

**The next `python3 build_dashboard.py` run silently reverts both.** Apply those
two edits to the generator before regenerating, or re-apply the patches to the
output afterwards and re-run `ui_test_playwright.py`.

---

## 7. Real league data — confirmed, no placeholders

Asserted against live rendered text, not the source:

- **All three keepers present:** Kenneth Walker (KEEP R4, "2 yr left"), Bo Nix
  (KEEP R12, "1 yr left"), Jameson Williams (KEEP R14, "1 yr left").
- **All nine real rival handles present:** tlekes, havicht, jomud,
  LoochCarluccio, pdustin, PeterCrisileo, Edeecher, DannyBC1, jpalmeri1616 —
  with real team names ("Water, Barkley, and Hops", "Glizzy Guzzler", "Mass
  General Hospital", "Big Mommy Milkers (UCSF)").
- **andrewroth32 correctly excluded** from the OPPONENTS tab.
- Roster is real and specific: Jacoby Brissett, Ashton Jeanty (flagged
  `R1 — ineligible`), Puka Nacua R2, Travis Kelce R7, Mike Evans (WR · **SF**,
  Questionable/Quadriceps), Joe Mixon (**FA**, "effectively unrosterable"),
  Jacksonville Jaguars DEF.
- Draft content is real: pick map 8/13/28/33/48/53/68/73/88/93/108/113/128/133/
  148/153 with three FORFEIT cells (p33 Walker, p113 Nix, p133 Jameson) and the
  three 19-pick dead zones; the 30-second version names actual players
  ("28: QB2. Murray → Lawrence → Herbert → Mahomes → Purdy → Love").
- Waivers correctly resolved as **PRIORITY not FAAB**, Andrew at #4, with the
  unconfirmed-processing-day warning stating both readings.
- **Placeholder scan: zero hits** for lorem ipsum, "Player One", "Team A",
  "John Doe", "TODO:", "XXX", etc.

Empty panels are honestly labelled NO DATA with the producer named — e.g. bye
coverage says `league_config.nfl_bye_weeks_2026.byes is empty; cannot compute`,
and the trade board explains it needs a real `opponent_model`. That is a refusal
to guess, not a hole.

---

## 8. Human read of the screenshots

**Mobile (390×844) — readable and usable.** Type is 16px base with generous
line height. The 4×4 pick-map grid fits cleanly at 390px with the round label,
overall pick number and LIVE/FORFEIT status all legible; green/red coding reads
instantly. The stat tiles wrap sensibly instead of squeezing. The amber warn
boxes ("READ THIS FIRST", "PROCESSING DAY UNCONFIRMED") stand out without
shouting. Keeper badges (`KEEP R14`, `1 yr left`) sit beside the player name
without pushing anything off-screen. Long prose wraps; nothing is clipped or
cut mid-word. Nothing is cramped.

**Tab switching visibly works** — comparing `screenshot_tab_myteam.png` and
`screenshot_tab_waivers.png`, the highlighted tab moves, the strip scrolls, and
the entire panel body is different content.

**Desktop (1440×900) — clean.** All 7 tabs fit on one row, content is centred at
940px max-width, and the pick map lays out as a comfortable 10 + 6. Tables show
as proper tables. No overflow.

**Cosmetic nit, not filed as a bug:** on STATUS, the two-column
provenance table hits the generic ≤700px collapse rule and stacks into
`FIELD / VALUE` pairs, so five rows fill an entire phone screen. Correct
behaviour for the five-column injuries table, wasteful for a key/value one. If
the generator ever gets touched, tag key/value tables with a class that keeps
them side-by-side on mobile. STATUS is a diagnostic tab, so this is low priority.

**Also noted, upstream not UI:** the page has no `league_id` anywhere — the
builder never puts it in the payload. Minor provenance gap on a tab whose whole
job is provenance. And `Kenneth Walker · RB · KC` comes straight from the player
cache; I have no way to verify NFL team assignments from this sandbox, so treat
team abbreviations as Sleeper's data rather than as checked facts.

---

## Coverage the harness does not have

- **No real iOS/Safari run.** Chromium only. `backdrop-filter` on the sticky nav
  lacks the `-webkit-` prefix iOS Safari wants, but the nav background is
  `rgba(11,15,20,.97)` — effectively opaque — so it degrades invisibly.
- **No touch-gesture testing.** Momentum scrolling of the tab strip and drawer
  taps were driven programmatically, not by a finger.
- **Pre-season data only.** Every in-season panel (action card, claim sheet,
  drop candidates, trade board) is empty in this build, so their *rendered*
  layout at 390px is unverified by me. The builder's own report describes a
  synthetic Week 7 fixture exercised under a Node DOM shim; that proves the code
  paths run, not that they lay out.
- Andrew should still open this on his actual phone once before Aug 28.
