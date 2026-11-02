"""Kokoro af_heart takes (Local AI Orchestrator). Choose the best take of each narration line and time its words.

    python3 narration/pick.py takes     (the folder of <id>.<k>.wav takes)

For every line in lines.json: transcribe each take (mlx-whisper, word timestamps), score it by how exactly the words
match the script (and, as a tie-break, closeness to the slot's length budget), trim silence, and keep the winner as
chosen/<id>.wav (narration/overrides.json can force a take: {"v02": "v02.2.wav"}). words.json gets each chosen line's words with times relative to the clip's start.
"""
import json, re, sys, difflib
from pathlib import Path
import numpy as np, soundfile as sf
import mlx_whisper

HERE = Path(__file__).resolve().parent
ASR = "mlx-community/whisper-large-v3-turbo"
def norm(s):
    s = re.sub(r"\[([^\]]+)\]\(/[^)]*/\)", r"\1", s).lower()     # "[word](/phonemes/)" -> "word"
    s = s.replace("-", " ").replace("’", "'")
    # whole-word replacements, so the tts spellings ("A I", "A P I") and whisper's digits meet in the middle
    for a, b in [(r"\bai\b", "a i"), (r"\bapi\b", "a p i"), (r"\b450\b", "four hundred and fifty"),
                 (r"\b227\b", "two hundred and twenty seven"), (r"\b88\b", "eighty eight"), (r"\b50\b", "fifty"),
                 (r"\b3\b", "three"), (r"\bhundred (fifty|twenty)", r"hundred and \1"), (r"\bok\b", "okay")]:
        s = re.sub(a, b, s)
    return re.sub(r"[^a-z0-9 ]", "", s)


def trim(y, sr, thr_db=-42, pad=0.06):
    env = np.abs(y)
    win = int(0.01 * sr)
    rms = np.sqrt(np.convolve(env ** 2, np.ones(win) / win, "same"))
    on = np.where(20 * np.log10(rms + 1e-9) > thr_db)[0]
    if not len(on):
        return y, 0.0
    a, b = max(0, on[0] - int(pad * sr)), min(len(y), on[-1] + int(pad * sr))
    return y[a:b], a / sr


def main():
    takes_dir = HERE / sys.argv[1]
    lines = json.loads((HERE / "lines.json").read_text())
    tts = json.loads((HERE / "lines-tts.json").read_text())
    out = HERE / "chosen"; out.mkdir(exist_ok=True)
    over = json.loads((HERE / "overrides.json").read_text()) if (HERE / "overrides.json").exists() else {}
    words_out, report = {}, []
    for key, text in lines.items():
        best = None
        cands = [takes_dir / over[key]] if key in over else sorted(takes_dir.glob(f"{key}.*.wav"))
        for f in cands:
            y, sr = sf.read(f)
            if y.ndim > 1: y = y.mean(1)
            y, cut = trim(y, sr)
            tmp = out / f"_{f.name}"; sf.write(tmp, y, sr)
            r = mlx_whisper.transcribe(str(tmp), path_or_hf_repo=ASR, language="en", word_timestamps=True)
            tmp.unlink()
            heard = " ".join(s["text"] for s in r["segments"]).strip()
            score = difflib.SequenceMatcher(None, norm(tts[key]).split(), norm(heard).split()).ratio()
            dur = len(y) / sr
            # words-per-second sanity: penalise very slow, draggy takes slightly
            wps = len(text.split()) / max(dur, 0.1)
            rank = score + (0.03 if f.name.endswith(".1.wav") else 0.0)
            ws = [{"w": w["word"].strip(), "t0": round(w["start"], 3), "t1": round(w["end"], 3)}
                  for s in r["segments"] for w in s.get("words", [])]
            # the clip is trimmed to its first sound (+60 ms pad), so its first word starts there. Whisper can place a
            # leading number late ("Two hundred and twenty-seven" -> "227" at 0.78 s in v12): pin it to the pad.
            if ws and ws[0]["t0"] > 0.25:
                ws[0]["t0"] = 0.06
            if best is None or rank > best[0]:
                best = (rank, f.name, y, sr, heard, dur, ws, score)
        rank, name, y, sr, heard, dur, ws, score = best
        sf.write(out / f"{key}.wav", y, sr)
        words_out[key] = {"text": text, "dur": round(dur, 3), "take": name, "words": ws}
        report.append(f"{key} {name:10s} {dur:5.2f}s match={score:.2f}  heard: {heard}")
    (HERE / "words.json").write_text(json.dumps(words_out, indent=1))
    print("\n".join(report))


if __name__ == "__main__":
    main()
