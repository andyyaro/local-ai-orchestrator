"""The edit of the recorded take: which take frame plays on each film frame, keyed to the narration and the music
(adapted from EV-SIENT tools/conform.py and the Outbreak films' capture/edit.py).

    python3 -I capture/conform.py            -> assets/shots/<shot>.mp4, assets/edit.js (window.EDIT), assets/edit.json

The take (assets/rec/dash-run.mp4 + .json) has one video frame per captured frame; each frame keeps its take time
tt (capture/rec.py): "i" frames are 1/30 s of pointer, typing and scrolling (1x); "w" frames are real time while the
model works. A shot is a list of segments, contiguous in film time:

  ("play", t0, t1, a, b)   take frames a..b over film t0..t1, linear in take time (1x when the lengths agree)
  ("fast", t0, t1, a, b)   the same, but the i frames inside (scrolls that followed the run, the pointer) play at 1x
                           and the model's waiting plays at ONE factor that fills the rest: the film labels it
                           ("16x speed"); the factor is real time / film time, so the label is true
  ("hold", t0, t1, a)      frame a held (a freeze: the take is never shown faster than real time by a hold)

Times come from the narration (assets/vo.js, W(line, word)) and the music grid (sound/grid.json); cuts and the shot
starts sit on the scene windows (sound/timing.json, bar lines) or on beats. Frames are picked, never blended, so every
film frame is a real recorded frame. The pointer is given per film frame in the take's CSS px (1280 x 720 viewport):
the film draws the cursor. Marks (clicks, keys, agent rows completing, the views) come out in film seconds.
"""
from __future__ import annotations

import bisect
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 30
TAKE = "dash-run"
VO = json.loads((ROOT / "assets" / "vo.js").read_text().strip().removeprefix("window.VO = ").rstrip(";"))
GRID = json.loads((ROOT / "sound" / "grid.json").read_text())
TM = json.loads((ROOT / "sound" / "timing.json").read_text())
BEAT = GRID["bar"] / 4


def W(line, word, nth=0, end=False):
    hits = [w for w in VO[line]["words"] if w["w"].strip(".,:;!?").lower() == word.lower()]
    return hits[nth]["t1" if end else "t0"]


def beat(t, mode="near"):
    k = t / BEAT
    k = round(k) if mode == "near" else (int(k) + (1 if k % 1 > 1e-6 else 0) if mode == "up" else int(k))
    return round(k * BEAT, 3)


def fr(t):
    return round(t * FPS)


class Take:
    def __init__(self, name):
        self.meta = json.loads((ROOT / "assets" / "rec" / f"{name}.json").read_text())
        self.F = self.meta["frame"]
        self.tt = [f[1] for f in self.F]
        self.mode = [f[2] for f in self.F]
        self.n = len(self.F)
        self.marks = self.meta["marks"]
        # page events seen on w frames are the run's own (rows starting and completing). On i frames the status rows
        # flip "done"/"run" while the pointer hovers or opens them (the summary icon changes): those are dropped, except
        # the supervisor's row, which appears during the click on Run pipeline.
        self.events = [[f, lab] for f, lab in self.meta["events"]
                       if self.mode[f] == "w" or lab.startswith("supervisor:run")]
        self.hover_flips = [[f, lab] for f, lab in self.meta["events"] if [f, lab] not in self.events]

    def m(self, key, i=0):
        v = self.marks[key]
        return v[i] if isinstance(v, list) else v

    def ev(self, text, nth=0, after=0):
        """The frame of the nth page event whose label contains text (from frame `after` on)."""
        hits = [f for f, lab in self.events if text in lab and f >= after]
        return hits[nth]


def schedule(take, segs):
    """Film frame -> take frame for a list of segments; also the speed segments for the chip."""
    out, speeds, cuts = [], [], []
    prev = None
    for s in segs:
        kind, t0, t1 = s[0], s[1], s[2]
        f0, f1 = fr(t0), fr(t1)
        n = f1 - f0
        if n <= 0:
            continue
        first = s[3]
        if prev is not None and abs(first - prev) > 3:
            cuts.append({"t": round(f0 / FPS, 3), "from_frame": prev, "to_frame": first})
        prev = s[3] if kind == "hold" else s[4]
        if kind == "hold":
            out += [s[3]] * n
            continue
        a, b = s[3], s[4]
        if kind == "play":
            ta, tb = take.tt[a], take.tt[b]
            fac = (tb - ta) / (t1 - t0)
            for i in range(n):
                t = ta + (tb - ta) * i / n
                out.append(min(b, max(a, bisect.bisect_right(take.tt, t + 1e-6) - 1)))
            if fac > 1.05:
                speeds.append({"t0": round(t0, 3), "t1": round(t1, 3), "factor": round(fac, 2)})
            continue
        # fast: i frames at 1x, waiting at one factor
        i_time = sum(take.tt[k] - take.tt[k - 1] for k in range(a + 1, b + 1) if take.mode[k] == "i")
        w_time = sum(take.tt[k] - take.tt[k - 1] for k in range(a + 1, b + 1) if take.mode[k] == "w")
        room = (t1 - t0) - i_time
        assert room > 0.02, f"fast segment {t0}-{t1}: the 1x frames alone need {i_time:.2f} s"
        fac = w_time / room
        film = [0.0]
        for k in range(a + 1, b + 1):
            d = take.tt[k] - take.tt[k - 1]
            film.append(film[-1] + (d if take.mode[k] == "i" else d / fac))
        scale = (t1 - t0) / film[-1]
        for i in range(n):
            t = i / FPS / scale
            out.append(a + max(0, bisect.bisect_right(film, t + 1e-9) - 1))
        speeds.append({"t0": round(t0, 3), "t1": round(t1, 3), "factor": round(fac, 2),
                       "real_s": round(w_time, 1), "pointer_1x_s": round(i_time, 2)})
    # adjacent sped stretches at about the same factor are one stretch for the corner label
    merged = []
    for sp in speeds:
        if merged and abs(sp["t0"] - merged[-1]["t1"]) < 1.5 / FPS and abs(sp["factor"] / merged[-1]["factor"] - 1) < 0.1:
            m = merged[-1]
            film = (m["t1"] - m["t0"] - m.get("pointer_1x_s", 0)) + (sp["t1"] - sp["t0"] - sp.get("pointer_1x_s", 0))
            real = m.get("real_s", m["factor"] * (m["t1"] - m["t0"])) + sp.get("real_s", sp["factor"] * (sp["t1"] - sp["t0"]))
            m.update(t1=sp["t1"], real_s=round(real, 1), pointer_1x_s=round(m.get("pointer_1x_s", 0) + sp.get("pointer_1x_s", 0), 2),
                     factor=round(real / film, 2))
        else:
            merged.append(dict(sp))
    return out, merged, cuts


def label(fac):
    return f"{fac:.0f}× speed" if fac >= 9.5 else f"{fac:.1f}× speed".replace(".0×", "×")


def encode(take_mp4, frames, out, size):
    """Decode the take once over the frames used and write them, in film order, to the shot's mp4."""
    lo, hi = min(frames), max(frames)
    w, h = size
    fsz = w * h * 3 // 2
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(take_mp4), "-vf", f"select=between(n\\,{lo}\\,{hi})",
                            "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "yuvj420p", "-"],
                           stdout=subprocess.PIPE)
    # the take is full-range BT.601 (JPEG frames: yuvj420p, pc, bt470bg, as the Outbreak films' takes); the shots keep
    # exactly that, tagged, so nothing is range-converted twice (an untagged copy decoded with clipped whites)
    enc = subprocess.Popen(["nice", "-n", "5", "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuvj420p",
                            "-color_range", "pc", "-colorspace", "bt470bg", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuvj420p",
                            "-color_range", "pc", "-colorspace", "bt470bg", "-g", "10", "-bf", "0",
                            "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    cur_i, cur = lo - 1, None
    for want in frames:
        while cur_i < want:
            cur = dec.stdout.read(fsz)
            assert len(cur) == fsz, f"take ended at frame {cur_i}"
            cur_i += 1
        enc.stdin.write(cur)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.kill()
    dec.wait()
    assert enc.returncode == 0, out


def shown(f, src, cuts):
    """True if take frame f is reached in this shot (not before it, not after it, not skipped by a cut)."""
    return src[0] <= f <= src[-1] and not any(c["from_frame"] < f < c["to_frame"] for c in cuts)


def film_marks(src, f0, take, keys, cuts):
    """Each take frame index in keys -> the film time it first plays in this shot."""
    res = {}
    for k, fs in keys.items():
        for f in fs if isinstance(fs, list) else [fs]:
            t = next((round((f0 + i) / FPS, 3) for i, s in enumerate(src) if s >= f), None)
            if t is not None and shown(f, src, cuts):
                res.setdefault(k, []).append(t)
    return {k: v if len(v) > 1 else v[0] for k, v in res.items()}


shotlist_mod = None


def build(shots, take):
    take_mp4 = ROOT / "assets" / "rec" / f"{TAKE}.mp4"
    (ROOT / "assets" / "shots").mkdir(parents=True, exist_ok=True)
    edit = {"take": TAKE, "fps": FPS, "viewport": take.meta["viewport"], "size": take.meta["size"], "shots": {}}
    tick_frames = [f for f, lab in take.events if ":done" in lab]
    for name, (segs, notes) in shots.items():
        src, speeds, cuts = schedule(take, segs)
        f0 = fr(segs[0][1])
        out = ROOT / "assets" / "shots" / f"{name}.mp4"
        encode(take_mp4, src, out, take.meta["size"])
        for sp in speeds:
            sp["label"] = label(sp["factor"])
        keys = {k: v for k, v in take.marks.items()}
        keys["row_done"] = tick_frames
        allr = {**take.meta.get("rects", {}), **getattr(shotlist_mod, "EXTRA_RECTS", {})}
        rects = {k: dict(v) for k, v in allr.items() if min(src) <= v["frame"] <= max(src) + 10}
        for v in rects.values():
            # the film time from which the page looks as it did when the rect was measured
            v["t"] = next((round((f0 + i) / FPS, 3) for i, s in enumerate(src) if s >= v["frame"] - 3), None)
        edit["shots"][name] = {
            "start": round(f0 / FPS, 4), "dur": round(len(src) / FPS, 4), "src": f"assets/shots/{name}.mp4",
            "frames": src, "cursor": [take.F[k][3:6] for k in src], "speed": speeds, "cuts": cuts,
            "marks": film_marks(src, f0, take, keys, cuts), "rects": rects,
            "events": [[t, lab] for t, lab in ((next((round((f0 + i) / FPS, 3) for i, s in enumerate(src) if s >= f), None), lab)
                                                for f, lab in take.events if shown(f, src, cuts)) if t is not None],
            "notes": notes}
        s = edit["shots"][name]
        print(f"{name:8s} {s['start']:7.3f}-{s['start'] + s['dur']:7.3f}  take {src[0]}..{src[-1]}  "
              f"speed {[(x['t0'], x['t1'], x['label']) for x in speeds]}  cuts {[c['t'] for c in cuts]}")
    js = "window.EDIT = " + json.dumps(edit, separators=(",", ":")) + ";\n"
    (ROOT / "assets" / "edit.js").write_text(js)
    slim = {k: v for k, v in edit.items() if k != "shots"}
    slim["shots"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("frames", "cursor")} for k, v in edit["shots"].items()}
    (ROOT / "assets" / "edit.json").write_text(json.dumps(slim, indent=1) + "\n")
    return edit


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import shotlist  # capture/shotlist.py: the shot keys for this take (written once the take's frames are known)
    shotlist_mod = shotlist
    take = Take(TAKE)
    build(shotlist.shots(take, W, beat, TM), take)
