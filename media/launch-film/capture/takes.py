"""The film's one take: a REAL run in the real dashboard, recorded frame by frame (capture/rec.py).

    python3 -I capture/serve.py start
    <pw-venv>/bin/python -I capture/takes.py            -> assets/rec/dash-run.mp4 + dash-run.json, capture/run/
    python3 -I capture/serve.py stop

One browser session, in order (SPEC.md SHOTS s3-s6):
  the dashboard idles; the pointer clicks the Task box and types the audit's goal; it presses Run pipeline; the page
  scrolls to Progress; the run works (wait frames, real time; scrolls that follow it are eased on the wall clock);
  when loop 1's judge is done the pointer opens the judge row (its own verdict, "'pass': True") and the page scrolls
  to Score progression ("0/100", "Below threshold"); when loop 2's judge is done, if the fixer or judge CLAIMED the
  limit was met, that row is opened on the claim; the run finishes; the page scrolls to Run summary (framed so the
  "Run saved to:" caption, which shows the scratch path, stays below the fold), jumps past it to Validator failures
  (the film cuts there), and the pointer opens "Metrics summary (Phase 5)".
Nothing is staged: the goal is typed into the dashboard's own box and every word on screen is the run's.
Read only: no other form is touched, nothing is uploaded, the history selectbox is never used.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rec import ROOT, SCR, Rec  # noqa: E402

URL = "http://localhost:8501"
GOAL = "Write a 50-word summary of why sleep matters."
MAIN = 'section[data-testid="stMain"]'
VW, VH = 1280, 720
PARK_X = 1128.0                     # the pointer rests right of the 720 px column (281-1001) while the run works
RUNS = SCR / "repo" / "runs"
AGENTS = ["supervisor", "planner", "builder", "critic", "fixer", "judge", "synthesizer"]

SIG_JS = """() => {
  const main = document.querySelector('section[data-testid="stMain"]');
  const AG = %s;
  const rows = [];
  for (const e of main.querySelectorAll('[data-testid="stExpander"]')) {
    const s = e.querySelector('summary'); if (!s) continue;
    const parts = s.innerText.split('\\n').map(x => x.trim()).filter(Boolean);
    const label = parts[parts.length - 1] || '';
    if (!AG.includes(label)) continue;
    rows.push(label + ':' + (parts[0] === 'check' ? 'done' : parts[0] === 'error' ? 'error' : 'run'));
  }
  const t = main.innerText;
  return JSON.stringify({rows, loops: (t.match(/Loop \\d+ of \\d+/g) || []).length,
    score: t.includes('Score progression'), final: t.includes('Run summary'),
    history: /Open run details/.test(t), err: t.includes('Pipeline error')});
}""" % json.dumps(AGENTS)

FONT_PROBE = """() => { const seen = {};
  for (const el of document.querySelectorAll('section[data-testid="stMain"] *')) {
    const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!hasText) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    (seen[cs.fontFamily] = seen[cs.fontFamily] || []).push(el.tagName + ':' + el.textContent.trim().slice(0, 30)); }
  return seen; }"""
MONO = re.compile(r"mono|courier|menlo|consolas|monaco|code pro", re.I)

# the n-th status row with a label (0-based), its summary, and its expanded body
ROW_JS = """([label, k]) => {
  const main = document.querySelector('section[data-testid="stMain"]');
  const out = [];
  for (const e of main.querySelectorAll('[data-testid="stExpander"]')) {
    const s = e.querySelector('summary'); if (!s) continue;
    const parts = s.innerText.split('\\n').map(x => x.trim()).filter(Boolean);
    if (parts[parts.length - 1] === label) out.push(e);
  }
  const e = out[k]; if (!e) return null;
  e.setAttribute('data-film-row', label + k);
  return true;
}"""

# the viewport rect of the first text range matching a string inside an element (for push-ins)
RANGE_JS = """([sel, needle]) => {
  const root = document.querySelector(sel); if (!root) return null;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const i = n.textContent.indexOf(needle);
    if (i < 0) continue;
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + needle.length);
    const rs = [...r.getClientRects()];
    const x0 = Math.min(...rs.map(q => q.left)), y0 = Math.min(...rs.map(q => q.top));
    const x1 = Math.max(...rs.map(q => q.right)), y1 = Math.max(...rs.map(q => q.bottom));
    return [x0, y0, x1 - x0, y1 - y0];
  }
  return null;
}"""


def run_dir():
    ds = sorted(RUNS.glob("ui_*"))
    return ds[-1] if ds else None


def rect(pg, sel_or_loc):
    loc = pg.locator(sel_or_loc) if isinstance(sel_or_loc, str) else sel_or_loc
    b = loc.first.bounding_box()
    return [round(b["x"], 1), round(b["y"], 1), round(b["width"], 1), round(b["height"], 1)] if b else None


def keep_rect(r, key, value):
    if value:
        r.meta.setdefault("rects", {})[key] = {"frame": r.n, "rect": [round(v, 1) for v in value]}


def text_rect(pg, sel, needle):
    return pg.evaluate(RANGE_JS, [sel, needle])


def scroll_top(pg):
    return pg.evaluate("(s) => document.querySelector(s).scrollTop", MAIN)


def top_in_main(pg, loc):
    """The element's top in the scroll container's content coordinates."""
    b = loc.first.bounding_box()
    return scroll_top(pg) + b["y"]


CLAIM_POS = re.compile(r"\b(meet|meets|meeting|met|within|exactly|adhere|adheres|adhering|complies|comply|fits|under)\b", re.I)
CLAIM_NEG = re.compile(r"\b(exceed|exceeds|exceeding|over|too long|beyond|more than|condense|reduce|remove|trim|cut)\b", re.I)


def find_claim(text):
    """A sentence in which a model says the 50-word limit was met (the trial's "meets the 50-word limit exactly")."""
    for sent in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        if re.search(r"50[- ]word", sent) and CLAIM_POS.search(sent) and not CLAIM_NEG.search(sent):
            return sent.strip()
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--hide-scrollbars", "--force-color-profile=srgb"])
        ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=2, color_scheme="light",
                                  reduced_motion="no-preference")
        pg = ctx.new_page()
        log = []
        pg.on("console", lambda m: m.type == "error" and log.append(m.text[:200]))
        pg.goto(URL, wait_until="networkidle")
        pg.wait_for_selector("text=Local AI Orchestrator")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(1500)
        fonts = pg.evaluate(FONT_PROBE)
        bad = [f for f in fonts if MONO.search(f)]
        assert not bad, f"monospace on the page before the take: {bad}"

        r = Rec(pg, "dash-run", VW, VH)
        r.sig = lambda: pg.evaluate(SIG_JS)

        def label(old, new):
            o, n = json.loads(old), json.loads(new)
            out = [x for x in n["rows"][len(o["rows"]):]]
            out += [f"{b}" for a, b in zip(o["rows"], n["rows"]) if a != b]
            for k in ("loops", "score", "final", "history", "err"):
                if o[k] != n[k]:
                    out.append(f"{k}={n[k]}")
            return ", ".join(out) or "layout"
        r.sig_label = label
        state = {"j1": False, "claim": False, "follow": True}

        # ---------------------------------------------------------------- s3: the goal and Run pipeline
        r.mark("idle")
        r.hold(30)
        ta = pg.locator("textarea").first
        tb = ta.bounding_box()
        r.move(tb["x"] + 64, tb["y"] + 26, 22)
        r.hold(2)
        r.click(hold=3, after=3, name="task_click")
        r.mark("type_start")
        r.type(GOAL, pattern=(1, 1, 1, 1, 2))
        r.mark("type_end")
        r.hold(4)
        btn = pg.get_by_role("button", name="Run pipeline")
        bb = btn.bounding_box()
        r.move(bb["x"] + bb["width"] * 0.5 - 30, bb["y"] + bb["height"] * 0.55, 14)
        r.hold(3)
        r.click(hold=4, after=2, name="run_press")
        t_press = time.time()

        # the rerun draws Progress and the supervisor's row
        ok = r.wait_until(lambda: pg.locator(MAIN).get_by_text("Progress", exact=True).count() > 0
                          and '"rows":["supervisor' in pg.evaluate(SIG_JS), timeout=60)
        assert ok, "Progress never appeared"
        r.mark("progress_shown")
        r.move(PARK_X, r.y + 40, 14)
        prog = pg.locator(MAIN).get_by_text("Progress", exact=True)
        r.scroll(MAIN, max(0, top_in_main(pg, prog) - 30), 26)
        r.mark("progress_view")

        # ---------------------------------------------------------------- the run works
        def sig():
            return json.loads(pg.evaluate(SIG_JS))

        def newest_bottom():
            return pg.evaluate("""() => {
              const main = document.querySelector('section[data-testid="stMain"]');
              const els = [...main.querySelectorAll('[data-testid="stExpander"], .card-soft')]
                .filter(e => !e.closest('[data-testid="stSidebar"]'));
              const prog = [...main.querySelectorAll('h2')].find(h => h.innerText.trim() === 'Score progression');
              let b = 0; for (const e of els) { const r = e.getBoundingClientRect();
                if (prog && r.top > prog.getBoundingClientRect().top) continue; b = Math.max(b, r.bottom); }
              return b; }""")

        def follow():
            if not state["follow"] or r.wscroll:
                return
            b = newest_bottom()
            if b > VH - 64:
                r.wall_scroll(MAIN, scroll_top(pg) + (b - VH * 0.74), 7.0)
                r.mark_list("follow_scroll")

        def open_row(label, k, mark, needle=None, claim=None):
            """The pointer opens the k-th row named label (1x frames); returns the opened row's selector."""
            pg.evaluate(ROW_JS, [label, k])
            sel = f'[data-film-row="{label}{k}"]'
            summ = pg.locator(f"{sel} summary")
            sb = summ.bounding_box()
            if sb["y"] < 40 or sb["y"] + sb["height"] > VH - 120:          # bring the row into the upper half first
                r.scroll(MAIN, scroll_top(pg) + sb["y"] - VH * 0.30, 22)
                sb = summ.bounding_box()
            r.move(sb["x"] + 150, sb["y"] + sb["height"] / 2, 18)
            r.hold(3)
            r.click(hold=3, after=0, name=mark)
            r.hold(14)
            if callable(needle):
                needle = needle(sel)
                r.meta[mark + "_needle"] = needle
            if needle:
                tr = text_rect(pg, sel, needle)
                if tr and tr[1] + tr[3] > VH - 48:
                    r.scroll(MAIN, scroll_top(pg) + tr[1] + tr[3] - VH * 0.62, 24)
                keep_rect(r, mark + "_text", text_rect(pg, sel, needle))
            keep_rect(r, mark + "_row", rect(pg, sel))
            r.hold(4)
            return sel

        def on_frame():
            s = sig()
            if s["err"]:
                raise RuntimeError("Pipeline error in the take")
            rows = s["rows"]
            # loop 1's judge is done and loop 2 has begun: open the judge's own verdict
            if not state["j1"] and "judge:done" in rows and s["loops"] >= 2 and any(x.startswith("critic") for x in rows):
                state["j1"] = True
                state["follow"] = False
                if r.wscroll:                                   # let a follow scroll finish first
                    while r.wscroll:
                        r.shot("w")
                def verdict(sel):
                    body = pg.evaluate("(s) => document.querySelector(s).innerText", sel)
                    m = re.search(r"'total_score': \d+, 'pass': (True|False)", body)
                    return m.group(0) if m else None
                open_row("judge", 0, "judge1_open", needle=verdict)
                # then down to Score progression, the code's verdict
                r.move(PARK_X, r.y, 14)
                h = pg.locator(MAIN).get_by_text("Score progression", exact=True)
                met = pg.locator(f'{MAIN} [data-testid="stMetric"]').filter(has_text="Current score").first
                mb = met.bounding_box()
                r.scroll(MAIN, scroll_top(pg) + mb["y"] + mb["height"] - (VH - 70), 28)
                r.mark("score_view")
                keep_rect(r, "score_heading", rect(pg, h))
                keep_rect(r, "score_current", rect(pg, met))
                keep_rect(r, "score_status", rect(pg, pg.locator(f'{MAIN} [data-testid="stMetric"]').filter(has_text="Status").first))
                r.hold(6)
                state["follow"] = True
                return
            # loop 2's judge is done (loop 3 has begun): open the row whose model claimed the limit was met
            if state["j1"] and not state["claim"] and s["loops"] >= 3 and rows.count("judge:done") >= 2:
                state["claim"] = True
                d = run_dir()
                cands = []
                try:
                    j2 = json.loads((d / "loop02_judge.json").read_text())
                    c = find_claim(j2.get("rationale", ""))
                    if c:
                        cands.append(("judge", 1, c))
                except Exception as e:  # noqa
                    print("claim: judge file", e)
                try:
                    c = find_claim((d / "loop02_fixer.txt").read_text())
                    if c:
                        cands.append(("fixer", 0, c))
                except Exception as e:  # noqa
                    print("claim: fixer file", e)
                r.meta["claims"] = cands
                print("claims", cands, flush=True)
                if cands:
                    lab, k, c = cands[0]
                    state["follow"] = False
                    while r.wscroll:
                        r.shot("w")
                    # the visible needle: a short span of the claim sentence as the page shows it
                    m = re.search(r"[^,;:]*50[- ]word[^,;:.]*", c)
                    needle = (m.group(0).strip() if m else c)[:90]
                    r.meta["claim_needle"] = needle
                    r.meta["claim_row"] = f"{lab}{k}"
                    open_row(lab, k, "claim_open", needle=needle)
                    r.move(PARK_X, r.y, 14)
                    r.hold(2)
                    state["follow"] = True
                return
            follow()

        done = r.wait_until(lambda: sig()["history"] and sig()["final"], timeout=1800, on_frame=on_frame)
        assert done, "the run did not finish in 30 min"
        r.mark("final_shown")
        t_run = time.time() - t_press
        r.wait(3.0)                                             # the history section settles; the script ends
        r.mark("run_end")

        # ---------------------------------------------------------------- after the run: summary, validators, metrics
        state["follow"] = False
        if abs(r.x - PARK_X) > 2:
            r.move(PARK_X, 380, 14)
        mets = pg.locator(f'{MAIN} [data-testid="stMetric"]')
        fs = mets.filter(has_text="Final score").first
        fb = fs.bounding_box()
        saved = pg.locator(MAIN).get_by_text(re.compile(r"^Run saved to:")).first
        target = scroll_top(pg) + fb["y"] + fb["height"] - (VH - 30)
        r.scroll(MAIN, target, 42)
        sv = saved.bounding_box()
        assert sv["y"] >= VH, f"Run saved to is in frame at the summary: {sv}"
        r.mark("summary_view")
        keep_rect(r, "final_score", rect(pg, fs))
        keep_rect(r, "result", rect(pg, mets.filter(has_text="Result").first))
        keep_rect(r, "loops", rect(pg, mets.filter(has_text="Loops").first))
        keep_rect(r, "mode", rect(pg, mets.filter(has_text="Mode").first))
        r.hold(8)

        # the cut: past the captions to Validator failures
        vf = pg.locator(MAIN).get_by_text("Validator failures", exact=True)
        has_vf = vf.count() > 0
        if has_vf:
            want = scroll_top(pg) + vf.first.bounding_box()["y"] - 64
        else:
            want = scroll_top(pg) + pg.locator(MAIN).get_by_text("Score history", exact=True).first.bounding_box()["y"] - 64
        path_cap = pg.locator(MAIN).get_by_text(re.compile(r"^(Path selected|Database ID):")).last
        pb = path_cap.bounding_box()
        need = scroll_top(pg) + pb["y"] + pb["height"] + 12           # every caption above the fold
        r.jump(MAIN, max(want, need))
        pg.wait_for_timeout(150)
        sv = saved.bounding_box()
        assert sv["y"] + sv["height"] <= 0, f"Run saved to is in frame after the cut: {sv}"
        r.mark("validators_view")
        r.hold(2)
        if has_vf:
            cap = pg.locator(MAIN).get_by_text(re.compile(r"^A high Judge score cannot rescue"))
            keep_rect(r, "vf_heading", rect(pg, vf))
            keep_rect(r, "vf_caption", rect(pg, cap))
            keep_rect(r, "vf_table", rect(pg, pg.locator(f'{MAIN} [data-testid="stDataFrame"]').first))
        r.hold(6)

        # the pointer opens Metrics summary (Phase 5)
        msum = pg.locator(f'{MAIN} [data-testid="stExpander"] summary').filter(has_text="Metrics summary (Phase 5)").first
        mb = msum.bounding_box()
        if mb["y"] + mb["height"] > VH - 40:
            r.scroll(MAIN, scroll_top(pg) + mb["y"] - VH * 0.55, 24)
            mb = msum.bounding_box()
        r.move(mb["x"] + 180, mb["y"] + mb["height"] / 2, 20)
        r.hold(4)
        r.click(hold=3, after=0, name="metrics_open")
        r.hold(16)
        rt = pg.locator(MAIN).get_by_text(re.compile(r"^Total runtime:")).first
        rb = rt.bounding_box()
        r.move(PARK_X, r.y + 60, 14)
        r.scroll(MAIN, scroll_top(pg) + rb["y"] - 70, 30)
        sv = saved.bounding_box()
        assert sv["y"] + sv["height"] <= 0, f"Run saved to came back into frame: {sv}"
        r.mark("metrics_view")
        keep_rect(r, "runtime", rect(pg, rt))
        exp = pg.locator(f'{MAIN} [data-testid="stExpander"]').filter(has_text="Metrics summary (Phase 5)").first
        keep_rect(r, "role_table", rect(pg, exp.locator('[data-testid="stDataFrame"]').first))
        keep_rect(r, "calls_table", rect(pg, exp.locator('[data-testid="stDataFrame"]').nth(1)))
        r.hold(20)
        r.mark("end")

        # ---------------------------------------------------------------- checks and the run's own record
        fonts = pg.evaluate(FONT_PROBE)
        bad = [f for f in fonts if MONO.search(f)]
        page_text = pg.evaluate(f"document.querySelector('{MAIN}').innerText")
        d = run_dir()
        out = ROOT / "capture" / "run"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix in (".json", ".txt"):
                shutil.copy2(f, out / f.name)
        (out / "dashboard-text.txt").write_text(
            "\n".join(l for l in page_text.splitlines() if not l.startswith("Run saved to:") and "Run dir" not in l))
        extra = {"run_id": d.name, "run_wall_s": round(t_run, 1), "goal": GOAL, "fonts": sorted(fonts),
                 "mono_fonts": bad, "console_errors": log[:10], "url": URL,
                 "scroller": MAIN, "park_x": PARK_X}
        meta = r.finish(extra=extra)
        browser.close()
    print("run", d.name, "wall", round(t_run, 1), "s; marks", {k: v for k, v in meta["marks"].items() if k != "keys"})
    print("events", meta["events"])
    print("mono", bad)
    return meta


if __name__ == "__main__":
    main()
