"""Frame-by-frame recorder for the live dashboard (adapted from EV-SIENT capture/rec.py and the Outbreak films'
capture/rec.py).

Every frame is the real page, rendered by headless Chromium at 1280 x 720 CSS px and 2x density (2560 x 1440),
captured in sequence with CDP Page.captureScreenshot. The pointer is NOT in the screenshots: its position per frame
is saved, and the film draws the cursor on that path.

Two kinds of frame, because the work here is a real model run that cannot be put on a virtual clock (the backend's
llama3.2:3b calls take as long as they take):

  "i" (interaction) frames: one frame = 1/30 s of take time. Pointer moves, clicks, typing and scrolls are set per
      frame (eased, as a hand moves), and the page's CSS/Web Animations are slowed by the same factor the capture is
      slow (CDP Animation.setPlaybackRate), so hovers and expanders play at their true speed at 30 fps. These are the
      take's 1x moments.
  "w" (wait) frames: the model is working. Frames are taken at up to WAIT_FPS on the wall clock and keep their real
      time; the take's time advances by the real time between them. Animations run at 1.0. Scrolls that follow the
      run while it is working are eased on the wall clock too, so they stay smooth when the wait is shown sped up.

Each frame keeps: wall (s since the recording started), tt (take time: i frames add 1/30, w frames add the wall
delta), mode, pointer x/y (CSS px) and pressed. The conform (capture/conform.py) maps film time to take time; a stretch
shown faster than real time gets its factor from tt, which is real time there, and the film labels it.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The working folder (not kept): a clone of the repository in work/repo, its venv in work/venv, raw frames.
SCR = Path(__file__).resolve().parent.parent / "work"
FPS = 30
WAIT_FPS = 5.0


def eo(p):
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def ei(p):
    return 0.0 if p <= 0 else 2 ** (10 * (p - 1))


def eio(p):
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return ei(2 * p) / 2 if p < 0.5 else (1 + eo(2 * p - 1)) / 2


def hand(p):
    """Minimum-jerk: quick start, long settle, as a hand moves a mouse (EV-SIENT)."""
    p = min(1.0, max(0.0, p))
    return p ** 3 * (10 - 15 * p + 6 * p * p)


class Rec:
    def __init__(self, page, name, vw=1280, vh=720, dpr=2, quality=90):
        self.pg, self.name, self.vw, self.vh, self.dpr, self.quality = page, name, vw, vh, dpr, quality
        self.dir = SCR / "rec" / name
        shutil.rmtree(self.dir, ignore_errors=True)
        (self.dir / "f").mkdir(parents=True)
        self.n = 0
        self.frames = []            # [wall, tt, mode, x, y, down]
        self.marks = {}             # name -> frame (or list of frames)
        self.events = []            # [frame, label]: things the page did on its own (server events)
        self.meta = {}
        self.x, self.y, self.down = vw * 0.93, vh + 60.0, False
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.send("Animation.enable")
        self.rate = None
        self.dts = deque(maxlen=10)
        self.t0 = time.perf_counter()
        self.tt = 0.0
        self.last_wall = None
        self.last_mode = None
        self.wscroll = None         # (selector, y0, y1, wall start, duration) for a wall-clock scroll
        self.sig = None             # callable -> hashable summary of the page; changes are logged as events
        self.sig_label = None       # callable(old, new) -> label
        self._sig_last = None
        self._set_rate(1.0)

    # ---------- the page's own animation speed ----------
    def _set_rate(self, r):
        r = max(0.04, min(1.0, r))
        if self.rate is None or abs(r - self.rate) / self.rate > 0.15:
            self.cdp.send("Animation.setPlaybackRate", {"playbackRate": r})
            self.rate = r

    # ---------- frames ----------
    def _capture(self):
        # Playwright's screenshot renders at the context's 2x density (a bare CDP capture from a second session came
        # out at 1x) and hides the text caret, whose real-time blink would flicker on slowed-down frames.
        self.pg.screenshot(path=str(self.dir / "f" / f"{self.n:05d}.jpg"), type="jpeg", quality=self.quality,
                           caret="hide", animations="allow")

    def shot(self, mode="i"):
        if mode == "i":
            if self.dts:
                self._set_rate((1 / FPS) / (sum(self.dts) / len(self.dts)))
        else:
            self._set_rate(1.0)
            if self.wscroll:
                sel, y0, y1, ws, d = self.wscroll
                p = (time.perf_counter() - ws) / d
                self._scroll_set(sel, y0 + (y1 - y0) * hand(p))
                if p >= 1:
                    self.wscroll = None
        a = time.perf_counter()
        wall = a - self.t0
        self._capture()
        if mode == "i":
            self.dts.append(time.perf_counter() - a)
        if self.last_wall is None:
            self.tt = 0.0
        elif mode == "i":
            self.tt += 1 / FPS
        else:
            self.tt += max(1 / FPS, wall - self.last_wall)
        self.last_wall, self.last_mode = wall, mode
        self.frames.append([round(wall, 3), round(self.tt, 4), mode, round(self.x, 1), round(self.y, 1), int(self.down)])
        if self.sig:
            s = self.sig()
            if s != self._sig_last:
                if self._sig_last is not None:
                    self.events.append([self.n, self.sig_label(self._sig_last, s) if self.sig_label else str(s)])
                self._sig_last = s
        self.n += 1

    def hold(self, frames):
        """Dense 1x frames (something on the page may still be animating)."""
        for _ in range(frames):
            self.shot("i")

    def mark(self, name):
        self.marks[name] = self.n

    def mark_list(self, name):
        self.marks.setdefault(name, []).append(self.n)

    # ---------- the pointer ----------
    def move(self, x, y, frames, curve=hand, sub=3):
        x0, y0 = self.x, self.y
        dist = math.hypot(x - x0, y - y0)
        for i in range(1, frames + 1):
            for k in range(1, sub + 1):
                e = curve((i - 1 + k / sub) / frames)
                arc = math.sin(math.pi * e) * min(28.0, dist * 0.06)
                self.pg.mouse.move(x0 + (x - x0) * e, y0 + (y - y0) * e - arc)
            e = curve(i / frames)
            arc = math.sin(math.pi * e) * min(28.0, dist * 0.06)
            self.x, self.y = x0 + (x - x0) * e, y0 + (y - y0) * e - arc
            self.shot("i")

    def move_to(self, locator, frames, dx=0.0, dy=0.0, fx=0.5):
        b = locator.bounding_box()
        self.move(b["x"] + b["width"] * fx + dx, b["y"] + b["height"] / 2 + dy, frames)
        return b

    def park(self, x, y):
        """Put the pointer somewhere without recording the move (used only while it is off the window)."""
        self.x, self.y = x, y
        self.pg.mouse.move(x, y)

    def click(self, hold=3, after=0, name=None):
        self.pg.mouse.move(self.x, self.y)
        self.down = True
        self.pg.mouse.down()
        if name:
            self.mark(name)
        self.hold(hold)
        self.pg.mouse.up()
        self.down = False
        self.hold(after)

    def type(self, text, pattern=(1, 2, 1, 1, 2, 1)):
        for i, ch in enumerate(text):
            self.pg.keyboard.type(ch)
            self.mark_list("keys")
            self.hold(pattern[i % len(pattern)])

    # ---------- scrolling ----------
    def _scroll_get(self, sel):
        return self.pg.evaluate("(s) => document.querySelector(s).scrollTop", sel)

    def _scroll_set(self, sel, y):
        self.pg.evaluate("([s, y]) => { document.querySelector(s).scrollTop = y; }", [sel, y])

    def scroll(self, sel, to_y, frames, curve=hand):
        """A 1x scroll, eased per frame."""
        y0 = self._scroll_get(sel)
        for i in range(1, frames + 1):
            self._scroll_set(sel, y0 + (to_y - y0) * curve(i / frames))
            self.shot("i")

    def jump(self, sel, to_y):
        """An instant scroll (no frames): the film cuts here."""
        self._scroll_set(sel, to_y)

    def wall_scroll(self, sel, to_y, seconds=8.0):
        """A scroll eased on the wall clock, carried out by the next wait frames."""
        self.wscroll = (sel, self._scroll_get(sel), to_y, time.perf_counter(), seconds)

    def wait_until(self, cond, timeout=1500.0, on_frame=None):
        """Wait frames (real time, up to WAIT_FPS) until cond() is true; on_frame() may act between frames."""
        t_end = time.perf_counter() + timeout
        while True:
            a = time.perf_counter()
            self.shot("w")
            if cond():
                return True
            if on_frame:
                on_frame()
            if time.perf_counter() > t_end:
                return False
            rest = 1 / WAIT_FPS - (time.perf_counter() - a)
            if rest > 0 and not self.wscroll:
                time.sleep(rest)

    def wait(self, seconds):
        t_end = time.perf_counter() + seconds
        self.wait_until(lambda: time.perf_counter() >= t_end, timeout=seconds + 5)

    # ---------- output ----------
    def finish(self, crf=17, extra=None):
        meta = {"name": self.name, "fps": FPS, "frames": self.n, "viewport": [self.vw, self.vh], "dpr": self.dpr,
                "size": [self.vw * self.dpr, self.vh * self.dpr],
                "wall": round(self.frames[-1][0], 2) if self.frames else 0,
                "take_time": round(self.frames[-1][1], 3) if self.frames else 0,
                "columns": ["wall", "tt", "mode", "x", "y", "down"],
                "_doc": ("One video frame per captured frame (NOT real time). wall: s since the recording began; tt: take "
                         "time (i frames 1/30 s each = 1x human action; w frames real time while the model works); "
                         "mode i/w; x, y: pointer in CSS px of the 1280x720 viewport (the film draws the cursor); "
                         "down: pressed. marks: frame indexes. events: [frame, what the page did on its own]."),
                "marks": self.marks, "events": self.events, **self.meta, **(extra or {}), "frame": self.frames}
        out_dir = ROOT / "assets" / "rec"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{self.name}.mp4"
        subprocess.run(["nice", "-n", "5", "ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
                        "-i", str(self.dir / "f" / "%05d.jpg"), "-c:v", "libx264", "-preset", "medium",
                        "-crf", str(crf), "-pix_fmt", "yuv420p", "-g", "30", "-bf", "0", "-movflags", "+faststart",
                        str(out)], check=True)
        (out_dir / f"{self.name}.json").write_text(json.dumps(meta, separators=(",", ":")) + "\n")
        print(f"{self.name}: {self.n} frames, wall {meta['wall']} s, take time {meta['take_time']} s -> {out}")
        return meta
