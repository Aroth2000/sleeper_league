#!/usr/bin/env python3
"""
Playwright browser test for dashboard.html.

Real Chromium, real layout. Checks:
  1. loads at 390x844 (mobile) + screenshot
  2. loads at 1440x900 (desktop) + screenshot
  3. every tab clicks, right panel shows, all others hide
  4. JS console errors / page errors captured
  5. horizontal overflow at 390px (element-level, because body has overflow-x:hidden
     which hides the symptom from scrollWidth)
  6. real league data present, not placeholder text

Run:  python3 ui_test_playwright.py [path-to-dashboard.html]
Exit 0 = all pass.
"""
import json, os, re, sys, pathlib

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
DASH = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "dashboard.html"
SHOT_M = HERE / "screenshot_mobile.png"
SHOT_D = HERE / "screenshot_desktop.png"

TABS = ["draft", "myteam", "opp", "waivers", "trades", "keepers", "status"]

RIVALS = ["tlekes", "havicht", "jomud", "LoochCarluccio", "pdustin",
          "PeterCrisileo", "Edeecher", "DannyBC1", "jpalmeri1616"]
KEEPERS = ["Kenneth Walker", "Bo Nix", "Jameson Williams"]
PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|dolor sit amet|foo ?bar|placeholder text|TODO:|XXX|"
    r"Player (One|Two|A\b)|Team (One|Two|A\b)|John Doe|Jane Doe", re.I)

results = []
def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("  PASS  " if ok else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    return ok


OVERFLOW_JS = """
() => {
  const vw = window.innerWidth;
  const out = [], scrollers = [], clipped = [];
  const isScroller = (e) => {
    const ox = getComputedStyle(e).overflowX;
    return ox === "auto" || ox === "scroll";
  };
  const walk = (el) => {
    for (const c of el.children) {
      const r = c.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (isScroller(c)) {
        // a deliberate horizontal scroll region: its children may exceed it, that is fine
        if (c.scrollWidth > c.clientWidth + 1)
          scrollers.push({tag: c.tagName.toLowerCase(),
                          cls: (c.className||"").toString().slice(0,40),
                          scrollW: c.scrollWidth, clientW: c.clientWidth});
        continue;
      }
      // content wider than its own box while clipped => text is being cut off
      if (c.scrollWidth > c.clientWidth + 2 && getComputedStyle(c).overflowX === "hidden")
        clipped.push({tag: c.tagName.toLowerCase(),
                      cls: (c.className||"").toString().slice(0,40),
                      scrollW: c.scrollWidth, clientW: c.clientWidth,
                      txt: (c.textContent||"").trim().slice(0,50)});
      if (r.right > vw + 1) {
        out.push({
          tag: c.tagName.toLowerCase(),
          cls: (c.className && c.className.toString ? c.className.toString() : "").slice(0, 60),
          right: Math.round(r.right),
          w: Math.round(r.width),
          txt: (c.textContent || "").trim().slice(0, 70)
        });
      } else {
        walk(c);   // only descend when parent itself fits, to find the real culprit
      }
    }
  };
  walk(document.body);
  return {
    vw,
    bodyScrollWidth: document.body.scrollWidth,
    docScrollWidth: document.documentElement.scrollWidth,
    offenders: out.slice(0, 25),
    offenderCount: out.length,
    scrollers: scrollers.slice(0, 10),
    clipped: clipped.slice(0, 10)
  };
}
"""

VISIBLE_JS = """
(ids) => ids.map(id => {
  const p = document.getElementById("pn-" + id);
  const b = document.getElementById("tb-" + id);
  if (!p) return {id, missing: true};
  const st = getComputedStyle(p);
  return {
    id,
    display: st.display,
    visible: st.display !== "none" && p.getBoundingClientRect().height > 0,
    selected: b ? b.getAttribute("aria-selected") : null,
    chars: (p.textContent || "").trim().length,
    renderError: /render error/i.test(p.textContent || "")
  };
})
"""


def main():
    if not DASH.exists():
        print("MISSING: " + str(DASH)); return 2

    console_errors, page_errors, req_failed = [], [], []
    overflow_report = {}
    tab_text = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])

        # ---------- MOBILE ----------
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True,
                                  has_touch=True)
        pg = ctx.new_page()
        pg.on("console", lambda m: console_errors.append(m.type + ": " + m.text)
              if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: page_errors.append(str(e)))
        pg.on("requestfailed", lambda r: req_failed.append(r.url + " " + str(r.failure)))

        pg.goto(DASH.as_uri(), wait_until="load")
        pg.wait_for_timeout(400)

        print("\n=== 1. LOAD + MOBILE RENDER (390x844) ===")
        check("page has a <title>", bool(pg.title()), pg.title())
        nbtn = pg.locator("#tabs button").count()
        check("7 tab buttons rendered", nbtn == 7, "found %d" % nbtn)
        body_chars = pg.evaluate("document.body.innerText.trim().length")
        check("body has substantial text", body_chars > 2000, "%d chars" % body_chars)

        pg.screenshot(path=str(SHOT_M), full_page=False)
        print("  wrote " + str(SHOT_M))

        print("\n=== 4. JS ERRORS ===")
        check("no uncaught page errors", not page_errors, "; ".join(page_errors[:3]))
        check("no console errors", not [c for c in console_errors if c.startswith("error")],
              "; ".join(console_errors[:3]))
        check("no failed subresource requests", not req_failed, "; ".join(req_failed[:3]))

        print("\n=== 3. TAB SWITCHING (mobile) ===")
        for tid in TABS:
            btn = pg.locator("#tb-" + tid)
            btn.scroll_into_view_if_needed()
            btn.click()
            pg.wait_for_timeout(180)
            state = pg.evaluate(VISIBLE_JS, TABS)
            by = {s["id"]: s for s in state}
            me = by[tid]
            others_hidden = all(not by[o]["visible"] for o in TABS if o != tid)
            ok = me["visible"] and others_hidden and me["chars"] > 200 and not me["renderError"]
            check("tab '%s' shows, others hide" % tid, ok,
                  "visible=%s chars=%d others_hidden=%s renderErr=%s" %
                  (me["visible"], me["chars"], others_hidden, me["renderError"]))
            check("tab '%s' aria-selected=true" % tid, me["selected"] == "true", str(me["selected"]))
            # regression: the strip scrolls horizontally; the active tab must stay visible
            vis = pg.evaluate("""(id)=>{const b=document.getElementById('tb-'+id)
                .getBoundingClientRect();
                return {on:b.left>=-1&&b.right<=innerWidth+1,l:Math.round(b.left),
                        r:Math.round(b.right)};}""", tid)
            check("tab '%s' button stays on-screen when selected" % tid, vis["on"],
                  "left=%d right=%d vw=390" % (vis["l"], vis["r"]))
            tab_text[tid] = pg.evaluate(
                "document.getElementById('pn-%s').innerText" % tid)
            if tid in ("myteam", "waivers"):
                p = HERE / ("screenshot_tab_%s.png" % tid)
                pg.screenshot(path=str(p), full_page=False)
                print("  wrote " + str(p))
            if os.environ.get("DEEP_SHOTS"):
                d = pathlib.Path("/tmp/tabshots"); d.mkdir(exist_ok=True)
                for y in (0, 700, 1600, 2600):
                    pg.evaluate("window.scrollTo(0,%d)" % y)
                    pg.wait_for_timeout(120)
                    pg.screenshot(path=str(d / ("%s_%d.png" % (tid, y))))
                pg.evaluate("window.scrollTo(0,0)")

            # ---- 5. overflow, measured on every tab, at 390 ----
            o = pg.evaluate(OVERFLOW_JS)
            overflow_report[tid] = o

        print("\n=== 5. HORIZONTAL OVERFLOW @390px ===")
        for tid in TABS:
            o = overflow_report[tid]
            ok = o["offenderCount"] == 0
            det = ""
            if not ok:
                det = "; ".join("<%s class=%r> right=%d w=%d %r" %
                               (f["tag"], f["cls"], f["right"], f["w"], f["txt"])
                               for f in o["offenders"][:4])
            check("no element overflows 390px on '%s'" % tid, ok, det)
            check("no clipped/cut-off text on '%s'" % tid, not o["clipped"],
                  json.dumps(o["clipped"][:3]))
        check("documentElement.scrollWidth <= innerWidth",
              overflow_report["draft"]["docScrollWidth"] <= overflow_report["draft"]["vw"] + 1,
              "doc=%d vw=%d" % (overflow_report["draft"]["docScrollWidth"],
                                overflow_report["draft"]["vw"]))
        print("  (deliberate scroll regions, not counted as bugs: %s)"
              % json.dumps(overflow_report["draft"]["scrollers"]))

        # scrollable regions are legitimate; confirm tables that DO overflow are wrapped
        print("\n=== 5b. TAP TARGETS ===")
        small = pg.evaluate("""() => {
          const bad=[];
          document.querySelectorAll('#tabs button, summary, button').forEach(b=>{
            const r=b.getBoundingClientRect();
            if(r.height>0 && r.height<40) bad.push({t:(b.textContent||'').trim().slice(0,30),h:Math.round(r.height)});
          });
          return bad.slice(0,10);
        }""")
        check("all buttons/summaries >= 40px tall", not small, json.dumps(small))

        # ---------- 6. REAL DATA ----------
        print("\n=== 6. REAL LEAGUE DATA ===")
        alltext = "\n".join(tab_text.values())
        for k in KEEPERS:
            check("keeper present: " + k, k in alltext)
        missing_rivals = [r for r in RIVALS if r not in alltext]
        check("all 9 real rival handles present", not missing_rivals, "missing " + str(missing_rivals))
        check("andrewroth32 NOT listed as an opponent",
              "andrewroth32" not in tab_text.get("opp", ""))
        ph = PLACEHOLDER_RE.findall(alltext)
        check("no lorem/placeholder text", not ph, str(set(ph))[:120])
        if "1389753893356838912" not in alltext:
            print("  NOTE  league_id is not shown anywhere on the page "
                  "(not a rendering bug; the builder never puts it in the payload)")
        check("SUPERFLEX/SUPER_FLEX referenced", "SUPER_FLEX" in alltext or "Superflex" in alltext)

        ctx.close()

        # ---------- 2. DESKTOP ----------
        print("\n=== 2. DESKTOP RENDER (1440x900) ===")
        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
        pg2 = ctx2.new_page()
        d_err = []
        pg2.on("pageerror", lambda e: d_err.append(str(e)))
        pg2.goto(DASH.as_uri(), wait_until="load")
        pg2.wait_for_timeout(400)
        pg2.screenshot(path=str(SHOT_D), full_page=False)
        print("  wrote " + str(SHOT_D))
        check("desktop: no page errors", not d_err, "; ".join(d_err[:2]))
        o2 = pg2.evaluate(OVERFLOW_JS)
        check("desktop: no horizontal overflow", o2["offenderCount"] == 0,
              json.dumps(o2["offenders"][:3]))

        # deep link check
        pg2.goto(DASH.as_uri() + "#keepers", wait_until="load")
        pg2.wait_for_timeout(300)
        sel = pg2.evaluate("document.getElementById('tb-keepers').getAttribute('aria-selected')")
        check("deep link #keepers opens keepers tab", sel == "true", str(sel))
        ctx2.close()

        # ---------- 7. DEEP LINK ON A PHONE (regression) ----------
        print("\n=== 7. DEEP LINK @390px + CONTRAST ===")
        ctx3 = browser.new_context(viewport={"width": 390, "height": 844})
        pg3 = ctx3.new_page()
        for tid in TABS:
            pg3.goto(DASH.as_uri() + "#" + tid, wait_until="load")
            pg3.wait_for_timeout(280)
            r = pg3.evaluate("""(id)=>{const b=document.getElementById('tb-'+id)
                .getBoundingClientRect();
                return {on:b.left>=-1&&b.right<=innerWidth+1,
                        sel:document.getElementById('tb-'+id).getAttribute('aria-selected'),
                        y:Math.round(window.scrollY)};}""", tid)
            check("deep link #%s: tab selected AND visible, no page jump" % tid,
                  r["on"] and r["sel"] == "true" and r["y"] == 0, json.dumps(r))

        # contrast of the smallest secondary text against its real background
        pg3.goto(DASH.as_uri(), wait_until="load")
        pg3.wait_for_timeout(250)
        cratio = pg3.evaluate("""() => {
          const lum = (rgb) => {
            const c = rgb.map(v => { v/=255; return v<=0.03928 ? v/12.92
                                          : Math.pow((v+0.055)/1.055, 2.4); });
            return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2];
          };
          const parse = (s) => (s.match(/\\d+/g)||[0,0,0]).slice(0,3).map(Number);
          const bgOf = (el) => {
            let n = el;
            while (n && n !== document.documentElement) {
              const b = getComputedStyle(n).backgroundColor;
              if (b && b !== "rgba(0, 0, 0, 0)" && b !== "transparent") return parse(b);
              n = n.parentElement;
            }
            return [11,15,20];
          };
          let worst = 99, where = "";
          document.querySelectorAll('.dim, .small, .mut, td, .nodata').forEach(e => {
            if (!(e.textContent||"").trim()) return;
            if (e.offsetParent === null) return;
            const fg = parse(getComputedStyle(e).color), bg = bgOf(e);
            const a = lum(fg), b = lum(bg);
            const cr = (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);
            if (cr < worst) { worst = cr; where = (e.className||e.tagName)+": "
                              +(e.textContent||"").trim().slice(0,40); }
          });
          return {worst: Math.round(worst*100)/100, where};
        }""")
        check("smallest secondary text meets WCAG AA 4.5:1",
              cratio["worst"] >= 4.5, json.dumps(cratio))
        ctx3.close()
        browser.close()

    print("\n" + "=" * 64)
    fails = [r for r in results if not r[1]]
    print("%d checks, %d passed, %d FAILED" % (len(results), len(results) - len(fails), len(fails)))
    for n, _, d in fails:
        print("  FAILED: " + n + ("  -- " + d if d else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
