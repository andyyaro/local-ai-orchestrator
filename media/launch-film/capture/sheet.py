"""Contact sheets to LOOK at the take and the conformed shots (ffmpeg tile).

    python3 -I capture/sheet.py take  <outdir>     # the take: every mark and every page event, 5 x N tiles
    python3 -I capture/sheet.py shots <outdir>     # each shot: 24 frames evenly spaced, with film times
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tile(src, frames, out, cols=5, labels=None, width=512):
    sel = "+".join(f"eq(n\\,{f})" for f in frames)
    rows = (len(frames) + cols - 1) // cols
    vf = f"select='{sel}',scale={width}:-2"
    # (this ffmpeg has no drawtext: the tile order is written to a .txt beside the sheet instead)
    vf += f",tile={cols}x{rows}:padding=6:margin=6:color=white"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf, "-fps_mode", "passthrough",
                    "-frames:v", "1", "-q:v", "3", str(out)], check=True)
    return out


def take(outdir):
    meta = json.loads((ROOT / "assets/rec/dash-run.json").read_text())
    picks = {}
    for k, v in meta["marks"].items():
        if k == "keys":
            continue
        for f in v if isinstance(v, list) else [v]:
            picks[min(f, meta["frames"] - 1)] = k
    for f, lab in meta["events"]:
        picks.setdefault(f, lab)
    fs = sorted(picks)
    (Path(outdir) / "take-sheet.txt").write_text("\n".join(f"{i:3d}  frame {f:5d}  {picks[f]}" for i, f in enumerate(fs)))
    for i in range(0, len(fs), 30):
        tile(ROOT / "assets/rec/dash-run.mp4", fs[i:i + 30], Path(outdir) / f"take-sheet-{i // 30}.jpg", labels=True)
    print(len(fs), "frames on the take sheets")


def shots(outdir):
    edit = json.loads((ROOT / "assets/edit.json").read_text())
    for name, s in edit["shots"].items():
        n = round(s["dur"] * 30)
        fs = [round(i * (n - 1) / 23) for i in range(24)]
        tile(ROOT / s["src"], fs, Path(outdir) / f"shot-{name}.jpg", cols=6, width=420)
        print(name, [round(s["start"] + f / 30, 2) for f in fs])


if __name__ == "__main__":
    {"take": take, "shots": shots}[sys.argv[1]](sys.argv[2])
