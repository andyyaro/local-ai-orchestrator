"""Cut "Nostalgic Night" (Michael Ramir C., Mixkit 1112, Mixkit Stock Music Free License) to the Local AI Orchestrator film.

    python3 -I sound/music.py     # -> assets/audio/music.wav, sound/grid.json

Andy, 2026-11-01: "calm but not too calm". The track is relaxed, friendly hip-hop: 68 BPM with a backbeat (kick on 1
and 3, snare on 2 and 4; librosa reads it double-time at 136). Measured in the sound stage (librosa beat track, fitted
period 0.441174 s per eighth, checked on kick/snare onset peaks: residual 6 ms, drift 3 ms per 100 s; attacks measured
on the waveform 30 ms ahead of the onset-strength phase):
  quarter 0.882348 s, bar 3.529393 s, track bar n starts at 0.436 + 3.529393 n s (5 ms before each downbeat's attack).
  The harmony is a two-bar cycle: even bars sit on G/Bb, odd bars on D/A. Every join goes from an odd bar to an even
  bar, so the chord cycle never breaks.
Structure (RMS, band levels and kick/snare counts per bar):
  bars 0-19   drums from the top, four-bar phrases peaking on their last bar (3, 11, 15, 19); 12-15 the fullest
  bars 20-21  the breakdown (low-mids drop out; the kick drops out for half of bar 21) and a near-silent gap before
  bar 22      the groove re-enters at 78.08 s: THE DROP
  bars 22-33  the groove again, phrases 22-25, 26-29, 30-33 (a fill at the end of 33)
  bar 34      the track's own ending: the crash ringing, a last stab at 121.77 s, silent by about 123 s

The edit (joins on bar lines, 12 ms crossfades), film seconds:
  film  0.000- 3.529  bar 17           a light groove bar, low-passed (900 Hz), under the hook's first line
  film  3.529-10.588  bars 20-21       the breakdown; the low-pass opens until the build is full at the drop
  film 10.588-38.823  bars 22-29       THE DROP on "Local" (the lockup); the groove under the goal and the judge
  film 38.823-52.941  bars 12-15       the fullest phrase, building under the repair loops and "failed"
  film 52.941-63.529  bars 30-32       settled again under "locally" and the tests
  film 63.529-69.900  bars 33-34       the end card on the track's own ending (the last stab lands after "Mac")
"""
import json, subprocess
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parent.parent
TRACK = ROOT / "sound/track.mp3"            # Mixkit 1112, downloaded by hand (assets/audio/SOURCE.md)
SR = 48000
B0, BAR = 0.436, 8 * 0.441174              # 3.529392 s
tb = lambda n: B0 + n * BAR                # track time of bar n
fb = lambda k: k * BAR                     # film time of film bar k
SEGMENTS = [(fb(0), tb(17)), (fb(1), tb(20)), (fb(11), tb(12)), (fb(15), tb(30))]   # (film start, track start)
DROP, END_CARD = fb(3), fb(18)             # bar 22 lands at film 10.588; bar 33 at film 63.529
FILM_END = 69.9                            # 2097 frames; track 123.28, after the ending has rung out
XF = 0.012
LP_START, LP_FLAT = 900.0, fb(1)           # the hook's low-pass: flat 900 Hz for bar 17, then opening to the drop


def hook_filter(x):
    """A zero-phase low-pass that opens from 900 Hz to dry between film bar 1 and the drop. Built from several
    zero-phase copies crossfaded along the cutoff curve (zero phase, so neighbouring copies sum without combing)."""
    n = int(round(DROP * SR))
    cut = [LP_START, 1250, 1750, 2450, 3400, 4800, 6700, 9400, 13000, 18000]
    seg = x[:, :n]
    copies = [sosfiltfilt(butter(2, c, "low", fs=SR, output="sos"), seg, axis=1) for c in cut] + [seg]
    t = np.arange(n) / SR
    u = np.clip((t - LP_FLAT) / (DROP - LP_FLAT), 0, 1) ** 1.6       # stays dark through bar 20, opens in bar 21
    pos = u * (len(copies) - 1)                                       # fractional index into the copies
    i0 = np.minimum(pos.astype(int), len(copies) - 2); fr = pos - i0
    out = np.zeros_like(seg)
    for k in range(len(copies) - 1):
        m = i0 == k
        out[:, m] = copies[k][:, m] * (1 - fr[m]) + copies[k + 1][:, m] * fr[m]
    x = x.copy(); x[:, :n] = out
    return x


def main():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(TRACK), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    track = np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)
    n = int(round(FILM_END * SR))
    out = np.zeros((2, n))
    x = int(XF * SR); ramp = np.linspace(0, 1, x)
    for k, (f0s, t0s) in enumerate(SEGMENTS):
        f0 = int(round(f0s * SR)); f1 = int(round(SEGMENTS[k + 1][0] * SR)) if k + 1 < len(SEGMENTS) else n
        t0 = int(round(t0s * SR))
        seg = track[:, t0: t0 + (f1 - f0)]
        seg = np.pad(seg, ((0, 0), (0, (f1 - f0) - seg.shape[1])))
        if k > 0:
            out[:, f0 - x: f0] = out[:, f0 - x: f0] * (1 - ramp) + track[:, t0 - x: t0] * ramp
        out[:, f0:f1] = seg
    out = hook_filter(out)
    fi = int(0.25 * SR); out[:, :fi] *= np.linspace(0, 1, fi)
    fo = int(0.6 * SR); out[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5    # the ending is already near silence here
    import soundfile as sf
    (ROOT / "assets/audio").mkdir(parents=True, exist_ok=True)
    sf.write(ROOT / "assets/audio/music.wav", out.T.astype(np.float32), SR)
    r = lambda v: round(v, 3)
    film_bars = [r(fb(k)) for k in range(int(FILM_END / BAR) + 1)]
    grid = {"track": "Nostalgic Night (Michael Ramir C., Mixkit 1112)", "bpm": 68.0, "beat": r(BAR / 4),
            "pulse": r(BAR / 8), "bar": round(BAR, 6), "drop": r(DROP), "end_card": r(END_CARD),
            "track_ending": r(END_CARD), "last_stab": r(END_CARD + 121.77 - tb(33)), "duration": FILM_END,
            "segments": [[r(a), r(b)] for a, b in SEGMENTS],
            "segment_bars": ["17 (low-passed)", "20-29 (breakdown, the drop at 22)", "12-15", "30-34 (ending)"],
            "film_bars": film_bars, "film_half_bars": [r(fb(k / 2)) for k in range(int(2 * FILM_END / BAR) + 1)]}
    (ROOT / "sound/grid.json").write_text(json.dumps(grid, indent=1))
    print(f"music.wav {FILM_END} s; drop {DROP:.3f}, joins {fb(11):.3f} and {fb(15):.3f}, end card {END_CARD:.3f}, "
          f"last stab {grid['last_stab']:.2f}")


if __name__ == "__main__":
    main()
