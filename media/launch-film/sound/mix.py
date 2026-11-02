"""The Local AI Orchestrator soundtrack: Kokoro af_heart, "Nostalgic Night" (Michael Ramir C.) as a quiet bed, soft effects.

    python3 -I sound/mix.py

Inputs: assets/audio/music.wav (sound/music.py), narration/chosen/<id>.wav + narration/words.json (narration/pick.py),
sound/sfx-src/mixkit-<id>.mp3 (Mixkit free sound effects, Mixkit Sound Effects Free License; copied from secure-data-hub),
sound/sfx-cues.json (the picture's effect cues, written by sound/cues.py from index.html).
Outputs:
- assets/audio/mix.wav: the soundtrack, -16 LUFS integrated, true peak under -1.5 dBTP.
- assets/audio/vo.wav: the voice alone.
- assets/vo.js: window.VO, each line's start/end and word times in film seconds. Whisper writes numbers as digits:
  the cue words are "50", "450", "88", "3", "227" (and "-word" after "50"), e.g. W("v02", "88").
- assets/timing.js and sound/timing.json: window.TM, the scene windows. Every scene reads its start from it, and
  build.py writes the same numbers into index.html.

Levels (as secure-data-hub; Andy: "the sound should not be too loud, just present, the voice should be clear"):
- Speech at -16 LUFS. The bed sits 9 dB under the speech, and is ducked 4.5 dB more while she speaks
  (40 ms attack, 450 ms release), so it comes back up between lines.
- Each effect's peak lands one frame after its picture. Its loudest 100 ms (K-weighted) is set 3-6 dB over the bed's
  400 ms loudness at that moment (ducked or not), and at least 6.5 dB under the line she is speaking; report_effects()
  prints every effect measured on the finished stems. One vocabulary (sfx_events): a soft pop is a part arriving, a
  tick a step or a counter, an air whoosh the window travelling, a low pop code overruling a model, a riser and a soft
  hit on the drop, a lower click where the recorded pointer presses, single key taps under the typed goal.
- Order of a rebuild: this script, build.py, sound/cues.py (the picture's cues), then this script again.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, soundfile as sf, librosa

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
G = json.loads((ROOT / "sound/grid.json").read_text())
DROP, END_CARD, DUR = G["drop"], G["end_card"], G["duration"]

# each line's start in film seconds. The groove re-enters on the drop (10.588 s, film bar 3) on "Local"; the fullest
# phrase from 38.823 s under the repair loops; the track's own ending under the end card (63.529 s). See sound/music.py.
# Breaths of 0.45-0.75 s inside a beat; longer gaps only where the picture has work to show (typing the goal, the fast-path
# note, the push-in on the judge's words, the fixer's false claim, the scroll to the Run summary).
SLOTS = {"v01": 0.70, "v02": 4.25, "v03": 10.25, "v04": 12.65, "v05": 21.00, "v06": 28.75, "v07": 33.05, "v08": 39.25,
         "v09": 43.70, "v10": 47.35, "v11": 51.75, "v12": 58.65, "v13": 63.95}
# scene windows (film seconds), on the track's bar (3.529 s) and half-bar (1.765 s) lines: film bar k = 3.529392 k
_B = 3.529392
SCENES = {"s1": [0, round(3 * _B, 3)],                       # open: the July 2026 dot story, under the low-passed hook
          "s2": [round(3 * _B, 3), round(5.5 * _B, 3)],      # lockup on the drop
          "s3": [round(5.5 * _B, 3), round(8 * _B, 3)],      # the goal and the fast path
          "s4": [round(8 * _B, 3), round(11 * _B, 3)],       # the judge says pass; code forces zero
          "s5": [round(11 * _B, 3), round(14.5 * _B, 3)],    # the repair loops; Result Failed
          "s6": [round(14.5 * _B, 3), round(16.5 * _B, 3)],  # every call local (metrics)
          "s7": [round(16.5 * _B, 3), END_CARD],              # 227 tests
          "s8": [END_CARD, DUR]}                             # end card on the track's ending


def lufs(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summ = out[out.rfind("Summary:"):]
    i = float(summ.split("I:")[1].split("LUFS")[0])
    tp = float(summ.split("Peak:")[1].split("dBFS")[0]) if "Peak:" in summ else 0.0
    return i, tp


def to_stereo(y):
    return np.vstack([y, y]) if y.ndim == 1 else y


def load(path, sr=SR):
    y, s = sf.read(path, always_2d=True)
    y = y.T.astype(np.float64)
    if s != sr:
        y = np.vstack([librosa.resample(ch, orig_sr=s, target_sr=sr) for ch in y])
    return y


def main():
    words = json.loads((ROOT / "narration/words.json").read_text())
    music = load(ROOT / "assets/audio/music.wav")
    n = music.shape[1]

    # ---------------------------------------------------------------- the voice
    vo = np.zeros(n)
    meta, prev_end = {}, 0.0
    for key, t0 in SLOTS.items():
        y = load(ROOT / f"narration/chosen/{key}.wav").mean(0)
        if t0 < prev_end + 0.25:
            print(f"warning: {key} starts {prev_end + 0.25 - t0:.2f} s too early", file=sys.stderr)
        a = int(round(t0 * SR)); b = min(n, a + len(y))
        vo[a:b] += y[: b - a]
        end = t0 + len(y) / SR
        meta[key] = {"start": round(t0, 3), "end": round(end, 3), "text": words[key]["text"],
                     "words": [{"w": w["w"], "t0": round(t0 + w["t0"], 3), "t1": round(t0 + w["t1"], 3)} for w in words[key]["words"]]}
        prev_end = end
    tmp = Path(tempfile.mkdtemp())
    sf.write(tmp / "vo_raw.wav", vo.astype(np.float32), SR)
    # Kokoro is clean and bright already: a high-pass, a touch of presence, light de-essing and compression
    chain = ("highpass=f=80,equalizer=f=3000:t=q:w=1.2:g=1.5,equalizer=f=250:t=q:w=1.0:g=-1,"
             "deesser=i=0.2:f=0.5,acompressor=threshold=0.1:ratio=2.5:attack=10:release=150:makeup=1.3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "vo_raw.wav"), "-af", chain, "-ar", str(SR),
                    str(ROOT / "assets/audio/vo.wav")], check=True)
    vo = load(ROOT / "assets/audio/vo.wav").mean(0)[:n]
    vo = np.pad(vo, (0, n - len(vo)))

    # ---------------------------------------------------------------- the bed: quieter, less boom, ducked by the voice
    sf.write(tmp / "m.wav", music.T.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "m.wav"), "-af",
                    "bass=g=-4:f=110:w=0.7,equalizer=f=2500:t=q:w=1.5:g=-2", str(tmp / "m2.wav")], check=True)
    bed = load(tmp / "m2.wav")
    # measured as it plays: the mono voice goes to both channels, which reads 3 dB louder than a mono file
    # (secure-data-hub measured the mono file, so its bed sat about 12 dB under the voice, not 9)
    sf.write(tmp / "v.wav", np.vstack([vo, vo]).T.astype(np.float32), SR)
    vi, _ = lufs(tmp / "v.wav")
    bi, _ = lufs(tmp / "m2.wav")
    # speech at -16 LUFS. The EBU R128 gates (-70 LUFS absolute, -10 LU relative) already drop the digital silence
    # between lines, so the voice stem's integrated loudness IS the speech loudness: no correction for talk time
    # (secure-data-hub's correction made the speech about 1.4 dB quieter). report_levels() checks the result.
    vo *= 10 ** ((-16 - vi) / 20)
    bed *= 10 ** ((-25 - bi) / 20)            # the bed 9 dB under the speech before ducking
    # duck: -4.5 dB under the voice, 40 ms attack, 450 ms release (followed at 1 kHz, then interpolated)
    hop = SR // 1000
    env = np.sqrt(np.convolve(vo ** 2, np.ones(int(0.05 * SR)) / int(0.05 * SR), "same"))[::hop]
    on = (env > 10 ** (-45 / 20)).astype(float)
    g = np.empty(len(on)); state = 0.0
    att, rel = 1 - np.exp(-1 / (0.04 * 1000)), 1 - np.exp(-1 / (0.45 * 1000))
    for i, target in enumerate(on):
        state += (att if target > state else rel) * (target - state)
        g[i] = state
    g = np.interp(np.arange(n), np.arange(len(g)) * hop, g)
    duck = 10 ** (-4.5 * g / 20)
    bed *= duck

    # ---------------------------------------------------------------- effects
    # each one levelled against the bed as it plays at that moment (ducked or not): its loudest 100 ms (K-weighted) sits
    # its own 3-6 dB over the bed's 400 ms loudness there, and at least 6.5 dB under the line she is speaking
    TMd = {"drop": DROP, **SCENES}
    W = word_finder(meta)
    events = sfx_events(W, TMd, meta)
    vo2 = np.vstack([vo, vo])
    L_bed, L_vo = env_db(bed, 0.4), env_db(vo2, 0.4)
    kv = kweight(vo2)
    for m in meta.values():   # each line's loudness (K-weighted, over its own span)
        seg = kv[:, int(m["start"] * SR): int(m["end"] * SR)]
        LINES.append((m["start"], m["end"], float(-0.691 + 10 * np.log10((seg ** 2).sum(0).mean() + 1e-12))))
    sfx = np.zeros((2, n))
    groups = {}
    for ev in events:
        layer = sfx
        if ev.get("group"):
            layer = groups.setdefault(ev["group"], {"y": np.zeros((2, n)), "ev": []})
            layer["ev"].append(ev); layer = layer["y"]
        place(layer, ev, L_bed, L_vo)
    for gname, gr in groups.items():   # a run of overlapping hits (the typed goal): levelled as one sound
        t0, t1 = min(e["t"] for e in gr["ev"]), max(e["t"] for e in gr["ev"]) + 0.1
        le = env_db(gr["y"], 0.1)[int(t0 * 100): int(t1 * 100)]
        lb = float(np.mean(L_bed[int(t0 * 100): int(t1 * 100)]))
        over = gr["ev"][0]["over"]
        lv = max(voice_near(L_vo, e["t"] + 1 / 30) for e in gr["ev"])
        target = min(lb + over, lv - 6.5) if lv > -40 else lb + over
        gr["y"] *= 10 ** ((target - np.percentile(le, 90)) / 20)
        sfx += gr["y"]

    # ---------------------------------------------------------------- sum, level, limit
    mix = bed + sfx + vo2
    sf.write(tmp / "mix.wav", mix.T.astype(np.float32), SR)
    mi, _ = lufs(tmp / "mix.wav")
    mix *= 10 ** ((-16 - mi) / 20)
    report_levels(tmp, vo * 10 ** ((-16 - mi) / 20), bed * 10 ** ((-16 - mi) / 20), meta)
    report_effects(events, sfx, bed, vo2)
    sf.write(tmp / "mix2.wav", mix.T.astype(np.float32), SR)
    # sample peaks held at -2.6 dBFS: the inter-sample (true) peak then reads about -2 dBTP, which leaves room for
    # the AAC encode (0.79 gave -1.46 dBTP on this mix, over the -1.5 limit)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "mix2.wav"), "-af", "alimiter=limit=0.74:attack=3:release=60:level=disabled",
                    "-ar", str(SR), str(ROOT / "assets/audio/mix.wav")], check=True)
    fi, tp = lufs(ROOT / "assets/audio/mix.wav")

    (ROOT / "assets/vo.js").write_text("window.VO = " + json.dumps(meta) + ";\n")
    tm = {"drop": DROP, "end_card": END_CARD, "track_ending": G["track_ending"], "last_stab": G["last_stab"],
          "bar": G["bar"], "duration": DUR, **SCENES}
    (ROOT / "assets/timing.js").write_text("window.TM = " + json.dumps(tm) + ";\n")
    (ROOT / "sound/timing.json").write_text(json.dumps(tm, indent=1))
    print(f"mix.wav {DUR} s, {fi:.1f} LUFS, true peak {tp:.1f} dBTP; voice, bed and {len(events)} effects")
    print("lines: " + ", ".join(f"{k} {m['start']:.2f}-{m['end']:.2f}" for k, m in meta.items()))


def report_levels(tmp, vo, bed, meta):
    """Loudness of the final stems (after the master gain): the speech, the bed while she speaks and the bed between
    lines, each measured over its own stretches only (concatenated), so the printout is the bed-under-voice margin."""
    def cat(x, spans):
        x = np.atleast_2d(x)
        return np.concatenate([x[:, int(a * SR): int(b * SR)] for a, b in spans if b > a], axis=1)
    lines = sorted((m["start"], m["end"]) for m in meta.values())
    gaps = [(lines[i][1] + 0.5, lines[i + 1][0]) for i in range(len(lines) - 1) if lines[i + 1][0] - lines[i][1] > 0.9]
    out = {}
    for name, x, spans in (("speech", vo, lines), ("bed_speaking", bed, lines), ("bed_between", bed, gaps)):
        y = cat(x, spans)
        sf.write(tmp / f"lv_{name}.wav", (np.vstack([y[0], y[0]]) if y.shape[0] == 1 else y).T.astype(np.float32), SR)
        out[name] = lufs(tmp / f"lv_{name}.wav")[0]
    print(f"levels: speech {out['speech']:.1f} LUFS; bed {out['speech'] - out['bed_speaking']:.1f} dB under the voice "
          f"while she speaks, {out['speech'] - out['bed_between']:.1f} dB under between lines (ducking "
          f"{out['bed_between'] - out['bed_speaking']:.1f} dB)")
    return out


def word_finder(meta):
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    def W(k, w, nth=0):
        alts = w.split("|")
        ws = meta[k]["words"]
        for exact in (True, False):
            c = 0
            for x in ws:
                t = norm(x["w"])
                if any((t == a) if exact else t.startswith(a) for a in alts):
                    if c == nth: return x["t0"]
                    c += 1
        print(f"warning: no word {w!r} in {k}", file=sys.stderr)
        return meta[k]["start"]
    return W


# ==================================================================================================== the effects
# Mixkit free sound effects (Mixkit Sound Effects Free License), the same files as secure-data-hub's sound/sfx-src.
SFX = {
    "whoosh_wind": "mixkit-1465.mp3",   # Transition windy swoosh: the dots travelling in to the drop
    "whoosh_air": "mixkit-1492.mp3",    # Air woosh: the window settling, stepping aside, coming back, lifting away
    "tick": "mixkit-1120.mp3",          # Clear mouse click: a step (an agent row done, a line, a mark), a counter
    "pop": "mixkit-2357.mp3",           # light pop: a part arriving (a note, a chip, a tile); pitch 0.78 = a denial
    "pop_hard": "mixkit-3005.mp3",      # Hard pop click: the soft hit on the drop
    "typing": "mixkit-2538.mp3",        # Soft typing on a digital keyboard: cut into single keys for the typed goal
    "riser": "mixkit-2408.mp3",         # the swell into the drop
}
_cache = {}


def kweight(y):
    """ITU-R BS.1770 K-weighting at 48 kHz (the pre-filter of LUFS): a high shelf, then a high-pass."""
    from scipy.signal import lfilter
    y = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585], y, axis=-1)
    return lfilter([1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621], y, axis=-1)


def env_db(y, win):
    """Loudness (LUFS scale, K-weighted, channels summed) in a sliding window of `win` s centred on each 10 ms step."""
    z = kweight(np.atleast_2d(y))
    p = (z ** 2).sum(0)
    c = np.concatenate([[0.0], np.cumsum(p)])
    nn, w = len(p), int(win * SR)
    idx = np.arange(0, nn, SR // 100)
    a, b = np.clip(idx - w // 2, 0, nn), np.clip(idx + w // 2, 0, nn)
    return -0.691 + 10 * np.log10((c[b] - c[a]) / np.maximum(b - a, 1) + 1e-12)


def key_slices():
    """The typing take cut into single keystrokes, each from just before its onset (as EV-SIENT's sound/design.py)."""
    x = load(ROOT / "sound/sfx-src" / SFX["typing"]).mean(0)
    hop = SR // 1000
    e = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same"))[::hop]
    th = e.max() * 10 ** (-20 / 20)
    on, last = [], -10_000
    for i in range(1, len(e)):
        if e[i] > th >= e[i - 1] and i - last > 40:
            on.append(i); last = i
    out, L = [], int(0.085 * SR)
    for i in on:
        s = x[max(0, (i - 4) * hop): max(0, (i - 4) * hop) + L].copy()
        if len(s) < L:
            continue
        s[-int(0.01 * SR):] *= np.linspace(1, 0, int(0.01 * SR))
        out.append(np.vstack([s, s]) / (np.abs(s).max() + 1e-12))
    return out


def clip(name, pitch=1.0, var=0):
    """(stereo samples, peak time in s, loudest 100 ms in LUFS) for one effect, pitched by resampling."""
    key = (name, pitch, var)
    if key not in _cache:
        if name == "key":
            ks = _cache.setdefault("_keys", key_slices())
            y = ks[(var * 7) % len(ks)].copy()
        else:
            y = load(ROOT / "sound/sfx-src" / SFX[name])
            if name == "riser":    # let it swell in from nothing, and let its tail (0.5 s past the peak) fade, not stop
                f = int(1.2 * SR); y[:, :f] *= np.linspace(0, 1, f) ** 2
                f = int(0.4 * SR); y[:, -f:] *= np.linspace(1, 0, f) ** 2
        if pitch != 1.0:   # small pitch steps rotate repeated sounds (resampling also shortens or lengthens them)
            y = np.vstack([librosa.resample(ch, orig_sr=SR, target_sr=int(SR / pitch)) for ch in y])
        peak = np.argmax(np.convolve(np.abs(y).mean(0), np.ones(240) / 240, "same")) / SR
        _cache[key] = (y, peak, float(env_db(y, 0.1).max()))
    return _cache[key]


def place(out, ev, L_bed, L_vo):
    """Put one effect in, its peak one frame after its picture, its loudest 100 ms `over` dB over the bed there (the bed's
    400 ms loudness around the peak, or just before it for the riser), and at least 6.5 dB under the voice (the loudness of the line she is speaking)."""
    y, peak, lc = clip(ev["name"], ev.get("pitch", 1.0), ev.get("var", 0))
    tp = ev["t"] + 1 / 30
    k = int(round((tp - (0.2 if ev.get("pre") else 0)) * 100))
    lb = float(L_bed[min(max(k, 0), len(L_bed) - 1)])
    lv = voice_near(L_vo, tp)
    target = lb + ev["over"]
    if lv > -40:
        target = min(target, lv - 6.5)
    ev["bed"], ev["level"] = lb, target
    y = y * 10 ** ((target - lc) / 20 + ev.get("trim", 0) / 20)
    a = int(round((tp - peak) * SR))
    s0 = max(0, -a); a = max(0, a)
    b = min(out.shape[1], a + y.shape[1] - s0)
    out[:, a:b] += y[:, s0: s0 + (b - a)]


LINES = []   # (start, end, loudness) of each spoken line, filled by main()


def voice_near(L_vo, tp):
    """The loudness of the line she is speaking within 0.3 s of a moment; -99 when she is not."""
    return max([l for a, b, l in LINES if a - 0.3 <= tp <= b + 0.3], default=-99.0)


def report_effects(events, sfx, bed, vo2):
    """Measured on the finished stems: each effect's loudest 100 ms against the bed and the voice at that moment."""
    Ls, Lb, Lv = env_db(sfx, 0.1), env_db(bed, 0.4), env_db(vo2, 0.4)
    rows, bad, held = [], 0, 0
    for ev in sorted(events, key=lambda e: e["t"]):
        if ev.get("group"):
            continue
        tp = ev["t"] + 1 / 30
        a, b = int((tp - 0.05) * 100), int((tp + 0.08) * 100)
        ls = float(Ls[a:b].max())
        lb = float(Lb[int(round((tp - (0.2 if ev.get("pre") else 0)) * 100))])
        lv = voice_near(Lv, tp)
        cap = lv > -40 and ls >= lv - 6.6
        flag = ""
        if lv > -40 and ls > lv - 6:
            flag = "  <-- within 6 dB of the voice"
        elif ls - lb > 6.5 or (ls - lb < 2.5 and not cap):
            flag = "  <-- outside 3-6 dB"
        elif ls - lb < 2.5:
            flag = "  (held 6.5 dB under the voice over a loud bar of the bed)"; held += 1
        bad += flag.startswith("  <--")
        rows.append(f"  {ev['t']:6.2f}  {ev['name']:<11s} {ls - lb:+5.1f} dB over the bed"
                    + (f", {lv - ls:4.1f} dB under the voice" if lv > -40 else "") + flag)
    for g in sorted({e["group"] for e in events if e.get("group")}):
        ts = [e["t"] for e in events if e.get("group") == g]
        a, b = int((min(ts) + 1 / 30) * 100), int((max(ts) + 0.13) * 100)
        ls, lb = float(np.percentile(Ls[a:b], 90)), float(np.mean(Lb[a:b]))
        lv = max(voice_near(Lv, t) for t in ts)
        rows.append(f"  {min(ts):6.2f}  {g} ({len(ts)} keys to {max(ts):.2f}) {ls - lb:+5.1f} dB over the bed"
                    + (f", {lv - ls:4.1f} dB under the voice" if lv > -40 else ""))
    print("effects (film s, sound, loudest 100 ms vs the bed's 400 ms there):\n" + "\n".join(rows))
    print(f"effects outside 3-6 dB over the bed (with overlaps) or within 6 dB of the voice: {bad}; held under the voice: {held}")


def sfx_events(W, TM, meta):
    """The effects against the finished picture, in ONE vocabulary (as secure-data-hub): a soft pop is a part arriving, a
    tick a step or a counter, an air whoosh the window travelling, a low pop (pitch 0.78) code overruling a model, a riser
    and a soft hit on the drop; pointer clicks and key taps where the recorded pointer presses and types.
    Window cues come from the composition itself (sound/sfx-cues.json, written by sound/cues.py from index.html); the
    title scenes' cues are their word times, as compositions/s1, s2, s7 and s8 compute them.
    Each event: t (the picture's moment), name, over (dB over the bed), pitch; "pre" levels against the bed before it."""
    C = json.loads((ROOT / "sound/sfx-cues.json").read_text())
    S, CUE, AD = C["sfx"], C["cue"], C["aside_d"]
    e = []
    E = lambda t, name, over, pitch=1.0, **kw: e.append({"t": round(t, 3), "name": name, "over": over, "pitch": pitch, **kw})

    # s1, the hook: the opening air; the 50 asked for arrive; the count runs 50 -> 450 as the rest spiral out (a tick
    # every 50); the "88/100 · Passed" chip; the words draw in to the dial's centre, the swell, the hit on the drop
    E(0.15, "whoosh_air", 3, 1.1)
    a50 = W("v01", "50")
    E(a50, "pop", 4, 1.0)
    c0, c1 = W("v02", "it"), W("v02", "450") + 0.75
    for k in range(2, 10):
        E(c0 + (50 * k - 50) / 400 * (c1 - c0), "tick", 3, 1.0 + 0.02 * (k - 2))
    E(W("v02", "88") - 0.02, "pop", 4, 1.06)
    E(TM["drop"] - 0.15, "whoosh_wind", 3, 1.0)
    E(TM["drop"], "riser", 3, 1.0, pre=True)
    E(TM["drop"], "pop_hard", 5, 0.9)
    # s2, the lockup: the dial's pointer settles on its dot; the line's three parts; (the rule is the voice's)
    E(TM["s2"][0] + 0.3 + 1.25, "tick", 3, 0.94)
    E(W("v04", "seven") - 0.04, "tick", 3, 1.0)
    E(W("v04", "agents") + 0.31, "tick", 3, 1.05)
    E(W("v04", "no") - 0.04, "tick", 3, 1.1)

    # s3-s6, the dashboard window
    wh = S["whoosh"]
    E(wh[0][0] + 0.15, "whoosh_air", 4, 1.0)                    # the window settles (power3.out: fastest at the start)
    for t, d in wh[1:5]:                                          # steps aside and back (EIO: fastest halfway)
        E(t + d / 2, "whoosh_air", 4, 1.12)
    E(wh[5][0] + wh[5][1] / 2, "whoosh_air", 4, 1.06)            # the screen swap past loop 3, through the bare stage
    E(wh[6][0] + 0.4, "whoosh_air", 4, 0.94)                     # the "up" exit (power2.in: fastest at the end)
    for t in S["clicks"]:                                          # the recorded pointer presses
        E(t, "tick", 4, 0.86)
    for k, t in enumerate(sorted(S["keys"])):                      # the goal, typed (two keys in one frame: half a frame apart)
        prev = sorted(S["keys"])[k - 1] if k else -1
        E(t + (0.017 if abs(t - prev) < 0.005 else 0), "key", 3, 1.0, var=k, group="typing",
          trim=float(np.random.default_rng(k).uniform(-2, 1)))
    chip22, chip114 = S["pops"][5], S["pops"][6]
    for t in S["pops"][:5] + [chip114]:                            # notes and chips arriving
        if abs(t - a50) < 0.01 or abs(t - W("v02", "88")) < 0.05:
            continue                                               # (the hook's chip is placed above)
        if abs(t - W("v12", "50")) < 0.05:
            continue                                               # (the test's name: placed with the count below)
        E(t, "pop", 4, 1.0)
    # (the "22× speed" chip fades in 17 ms after the Run pipeline press: the click carries that moment)
    E(CUE["note3"] + 0.4, "tick", 3, 1.1)                         # the path note's segmented control selects "fast"
    for t in S["ticks"]:                                           # an agent row completes (one moment, one sound)
        if any(abs(t - x["t"]) < 0.2 for x in e if x["name"] in ("tick", "pop")):
            continue
        E(t, "tick", 3, 1.0)
    for t in S["thuds"]:                                           # code overrules a model: the forced zero, Failed
        E(t, "pop", 5, 0.78)
    for t in S["rings"]:                                           # a word mark lands on what the voice names
        if any(abs(t - x["t"]) < 0.3 for x in e if x["name"] in ("pop", "tick")):
            continue
        E(t, "tick", 3, 1.16)

    # s7: the count runs 0 -> 227 (power2.out): a tick every 25; it lands with "tests passed"; the test's name arrives
    k0, k1 = S["counter"]
    for k in range(1, 10):
        E(k0 + (1 - np.sqrt(1 - 25 * k / 227)) * (k1 - k0), "tick", 3, 1.0 + 0.025 * (k - 1))
    E(k1, "pop", 4, 1.06)
    E(W("v12", "50"), "pop", 4, 1.0)
    # s8: the lockup lands; the line under it; the address
    E(TM["s8"][0] + 0.25, "pop", 5, 1.0)
    E(W("v13", "private") - 0.04, "tick", 3, 1.06)
    E(W("v13", "runs") - 0.04, "tick", 3, 1.12)
    return e


if __name__ == "__main__":
    main()
