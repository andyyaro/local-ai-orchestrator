"""Write the scene windows (sound/timing.json, made by sound/mix.py) and the take's clip windows (assets/edit.json, made by
capture/conform.py) into index.html.

    python3 -I build.py

Each scene host's data-start/data-duration, each recorded shot's <video> data-start/data-duration and the root duration
come from the same numbers the scenes read at runtime (window.TM in assets/timing.js, window.EDIT in assets/edit.js), so
the two can never drift apart.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TM = json.loads((ROOT / "sound/timing.json").read_text())
EDIT = json.loads((ROOT / "assets/edit.json").read_text())
HOSTS = {"s1-open": "s1", "s2-lockup": "s2", "s3-goal": "s3", "s4-judge": "s4", "s5-repair": "s5", "s6-local": "s6",
         "s7-tests": "s7", "s8-end": "s8"}
r = lambda x: f"{x:.4f}".rstrip("0").rstrip(".")

if not (ROOT / "index.html").exists():
    raise SystemExit("build.py: no index.html yet (the composition stage writes it); sound/timing.json is ready")
s = (ROOT / "index.html").read_text()
for host, key in HOSTS.items():
    a, b = TM[key]
    s, n = re.subn(rf'(<div id="{host}"[^>]*?data-start=")[^"]*(" data-duration=")[^"]*(")', rf"\g<1>{r(a)}\g<2>{r(b - a)}\g<3>", s)
    assert n == 1, host
for name, shot in EDIT["shots"].items():
    s, n = re.subn(rf'(<video id="v-{name}"[^>]*?data-start=")[^"]*(" data-duration=")[^"]*(")',
                   rf"\g<1>{r(shot['start'])}\g<2>{r(shot['dur'])}\g<3>", s)
    assert n == 1, name
s, n = re.subn(r'(<div id="main"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{r(TM['duration'])}\g<2>", s); assert n == 1
s, n = re.subn(r'(<audio id="soundtrack"[^>]*?data-duration=")[^"]*(")', rf"\g<1>{r(TM['duration'])}\g<2>", s); assert n == 1
(ROOT / "index.html").write_text(s)
print("index.html:", ", ".join(f"{k} {TM[k][0]}-{TM[k][1]}" for k in HOSTS.values()), f"| {TM['duration']} s")
print("clips:", ", ".join(f"{k} {v['start']}+{v['dur']}" for k, v in EDIT["shots"].items()))
