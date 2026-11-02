# Local AI Orchestrator launch film

The 70-second film at the top of the [repository README](../../README.md), published at
https://andyyaro.github.io/local-ai-orchestrator/film.html. It opens on a real bug from July 2026:
a 50-word summary was asked for, about 450 words came back, and the run still scored 88/100 and
passed. Then the same goal in the real Streamlit dashboard today: the judge model calls a
too-long draft a pass, plain code counts the words and forces the score to zero, the critic and
fixer try again, and after three loops the run reports Failed. The dashboard in it is a screen
recording of that one run, every call on llama3.2:3b; the model's work plays faster than real
time and the corner of the window says by how much.

[STORYBOARD.md](STORYBOARD.md) has the scenes, the look, the sound and every build step.
[FACTS.md](FACTS.md) has every claim in the film and where it comes from, and
[SPEC.md](SPEC.md) is the full brief the film was built to.

## What is here

| Path | What it is |
|---|---|
| `index.html`, `compositions/` | The composition (HyperFrames 0.8.173, GSAP): the dashboard window, its camera, the drawn cursor and the speed chip in `index.html`, and one file per scene |
| `build.py` | Writes the scene windows and the recorded shots' windows into the composition |
| `assets/cues.js`, `assets/vo.js`, `assets/timing.js`, `assets/edit.js` | What the scenes read: the shared eases and cue points, every narrated word's film time, the scene windows, and the edit of the take (which recorded frame plays on each film frame, the pointer, the sped-up stretches and the boxes the camera pushes in on); `assets/edit.json` is a short copy of the edit |
| `capture/` | The take: `serve.py` starts and stops the real dashboard, `takes.py` and `rec.py` record it frame by frame in Chromium with the pointer's path saved, `shotlist.py` and `conform.py` cut it into shots and write the edit, `sheet.py` makes contact sheets |
| `capture/run/` | The run's own files: the supervisor's refined goal, every draft, the judge's verdicts, the validators' results and the run summary |
| `assets/rec/dash-run.json` | The take's frame log: the time of each frame, the pointer and the page's events |
| `narration/` | The script (`lines.json`), the script as voiced (`lines-tts.json`), `pick.py`, which chooses the best take of each line and times its words (`words.json`), and `vtt.py`, which writes the captions file. `lines-variant-b.json` holds two lines for a run that passes; the film's run failed, so they are not used |
| `sound/` | The music edit (`music.py`, `grid.json`), the mix (`mix.py`, `timing.json`) and `cues.py`, which reads the effect cues out of the composition (`sfx-cues.json`) |
| `FACTS.md` | Every line of narration and every on-screen claim, with its source |
| `SPEC.md` | The brief: goal, sound, look, motion, shots, capture and the take |
| `tools/fetch_vendor.sh` | Fetches GSAP at the pinned version and checks the file's SHA-256 |
| `deploy/film.html`, `deploy/index.html`, `deploy/logo.svg` | The watch page, a redirect to it from the site's root, and the page's logo (the film's lockup with the wordmark in cream) |
| `assets/brand/wordmark-forest.svg` | The wordmark in the brand's forest green, as the film sets it; the other logo files are in [docs/assets/brand/](../../docs/assets/brand/) |
| `assets/audio/SOURCE.md` | Every third-party sound and font in the film, with its licence and where it goes |
| `ruff.toml` | Keeps the film's scripts out of the project's lint in CI, which runs `ruff check .` from the repository root |

## What is not here, and why

The working folder for the film is about 115 MB. This folder keeps the source and leaves out
everything that is generated or that its licence does not let us hand on by itself:

- **Generated:** the recorded shots (`assets/shots/`), the narration takes and the chosen takes,
  the music edit, the voice and the mix (`assets/audio/`), contact sheets and snapshots, and the
  renders, the captions file included. The build steps make them again.
- **The screen recording** of the run (`assets/rec/dash-run.mp4`, 13.8 MB) and the working folder
  it was recorded in (a clone of this repository with its own venv and a fresh `runs/`).
  `assets/rec/dash-run.json` and `capture/run/` say what is in it.
- **Third-party media:** the music ("Nostalgic Night" by Michael Ramir C., Mixkit) and seven
  Mixkit sound effects. [assets/audio/SOURCE.md](assets/audio/SOURCE.md) lists each one with its
  licence and the path it goes to.
- **Libraries and fonts:** GSAP 3.14.2 is fetched by `tools/fetch_vendor.sh`. The Inter and Inter
  Display fonts (SIL OFL 1.1) go in `assets/fonts/`. `node_modules/` and `.hyperframes/` are made
  by HyperFrames.

## Publishing

The MP4, its captions and its poster are assets of the
[`film-v1` release](https://github.com/andyyaro/local-ai-orchestrator/releases/tag/film-v1), so the
14.2 MB film is not in the repository's history. The
[film page workflow](../../.github/workflows/film.yml) puts them on GitHub Pages with
`deploy/film.html`, `deploy/index.html`, `deploy/logo.svg` and the favicon. It runs when anything in
`deploy/` changes on `main`. After replacing a release asset, run it by hand:

```sh
gh release upload film-v1 local-ai-orchestrator-launch.mp4 --clobber
gh workflow run film.yml
```

## Credits

Narration: Kokoro-82M (Apache-2.0), voice af_heart. Music: "Nostalgic Night" by Michael Ramir C.
(Mixkit). Sound effects: Mixkit. Type: Inter and Inter Display (SIL OFL 1.1); the wordmark is
Familjen Grotesk Bold (SIL OFL 1.1), outlined in the logo files. The dashboard is this project's
own Streamlit app, recorded as it ran.
