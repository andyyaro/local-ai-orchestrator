"""Read the picture's effect cues out of the composition, for sound/mix.py.

    <pw-venv>/bin/python -I sound/cues.py

Loads index.html in headless Chromium (Playwright) and writes sound/sfx-cues.json: window.__SFX (pointer presses, key
taps, agent rows completing, window moves, notes and chips arriving, the two overrules, the word marks, the 227 count)
and window.FILM.CUE (the window's cue points), all in film seconds. index.html computes them from the same numbers it
animates with (assets/edit.js, assets/vo.js, assets/timing.js), so the effects follow the picture.

Order: sound/mix.py (vo.js, timing.js) -> python3 -I build.py -> sound/cues.py -> sound/mix.py again (the effects).
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "index.html").as_uri())
    pg.wait_for_function("window.__SFX && window.FILM && window.FILM.CUE", timeout=20000)
    cues = pg.evaluate("({ sfx: window.__SFX, cue: window.FILM.CUE, aside_d: window.FILM.ASIDE_D })")
    b.close()
if errs:
    sys.exit("page errors: " + "; ".join(errs))
(ROOT / "sound/sfx-cues.json").write_text(json.dumps(cues, indent=1))
s = cues["sfx"]
print(f"sound/sfx-cues.json: {len(s['clicks'])} presses, {len(s['keys'])} keys, {len(s['ticks'])} rows, "
      f"{len(s['whoosh'])} window moves, {len(s['pops'])} arrivals, {len(s['thuds'])} overrules, {len(s['rings'])} marks")
