"""Write the film's English subtitles from the narration: renders/local-ai-orchestrator-v1.en.vtt.

    python3 -I narration/vtt.py

Text from narration/lines.json (the script as spoken), times from assets/vo.js (each line's start and end in film
seconds, as sound/mix.py placed it). One cue per line, wrapped to two rows of at most 48 characters (a line too long for that becomes two cues,
split at a comma on the voice's own word time).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINES = json.loads((ROOT / "narration/lines.json").read_text())
s = (ROOT / "assets/vo.js").read_text()
VO = json.loads(s[s.index("{"): s.rindex("}") + 1])


def ts(t):
    h, r = divmod(t, 3600); m, r = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{r:06.3f}"


def wrap(text, width=48):
    """Two rows: a split at a sentence end first, then at a colon or comma, then the most balanced. None if no split
    keeps both rows within the width."""
    if len(text) <= width:
        return text
    words = text.split()
    cands = []
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) <= width and len(b) <= width:
            rank = 0 if a.endswith(".") else 1 if a.endswith((":", ",")) else 2
            cands.append((rank, abs(len(a) - len(b)), a + "\n" + b))
    return min(cands)[2] if cands else None


norm = lambda w: "".join(c for c in w.lower() if c.isalnum())
cues = []
for key, text in LINES.items():
    m = VO[key]
    if wrap(text):
        cues.append((m["start"], m["end"] + 0.25, wrap(text)))
        continue
    # too long for two rows: two cues, split at the comma nearest the middle, timed by the voice's own word times
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if a.endswith(",") and wrap(a) and wrap(b):
            if best is None or abs(len(a) - len(b)) < best[0]:
                best = (abs(len(a) - len(b)), a, b)
    _, a, b = best
    t = next(w["t0"] for w in m["words"] if norm(w["w"]) == norm(b.split()[0]))
    cues.append((m["start"], t - 0.05, wrap(a)))
    cues.append((t, m["end"] + 0.25, wrap(b)))

out = ["WEBVTT", ""]
for n, (t0, t1, txt) in enumerate(cues, 1):
    out += [str(n), f"{ts(t0)} --> {ts(t1)}", txt, ""]
path = ROOT / "renders/local-ai-orchestrator-v1.en.vtt"
path.parent.mkdir(exist_ok=True)
path.write_text("\n".join(out))
print(f"{path.relative_to(ROOT)}: {len(cues)} cues from {len(LINES)} lines")
