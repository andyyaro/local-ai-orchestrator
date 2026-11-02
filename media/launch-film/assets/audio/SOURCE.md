# Third-party sounds, pictures and type in the film

These are in the film but not in this repository. Their licences cover using them inside a film,
not handing the files on by themselves, so they are listed here instead. Download each one again
to the path shown to rebuild.

## Music

| Used as | Track | Licence | Put it at |
|---|---|---|---|
| The bed under the whole film, cut on whole bars of its 68 BPM groove by `sound/music.py` | "Nostalgic Night" by Michael Ramir C., Mixkit 1112 | [Mixkit Stock Music Free License](https://mixkit.co/license/): free in any project, no credit required, not for use in a music-only track | `sound/track.mp3` |

## Sound effects

All from Mixkit, under the [Mixkit Sound Effects Free License](https://mixkit.co/license/).
The names are the ones `sound/mix.py` uses (`SFX`); each file goes in `sound/sfx-src/` as
`mixkit-<id>.mp3`. There are 105 effects in the film, all made from these seven files.

| Name in `mix.py` | Mixkit id | What it marks |
|---|---|---|
| `tick` | 1120 | A step or a counter: an agent row done, a line, a mark, the 50 to 450 and 0 to 227 counts; lower, each recorded pointer press |
| `pop` | 2357 | A part arriving: a note, a chip, a tile; pitched down, code overruling a model (the forced zero and "Failed") |
| `whoosh_air` | 1492 | The window settling, stepping aside, coming back and lifting away |
| `whoosh_wind` | 1465 | The dots travelling in to the drop |
| `riser` | 2408 | The swell into the drop |
| `pop_hard` | 3005 | The soft hit on the drop |
| `typing` | 2538 | Cut into single key taps under the typed goal |

## Voice

Kokoro-82M ([Apache-2.0](https://huggingface.co/hexgrad/Kokoro-82M)), voice af_heart, speed 1.0,
run locally. The lines are `narration/lines-tts.json`; the audio is generated, so it is not kept.

## Type

Inter and Inter Display, version 4.001 (the [Inter project](https://github.com/rsms/inter)), under
the [SIL Open Font License 1.1](https://openfontlicense.org/), for every word the film sets. They go
in `assets/fonts/` as `.woff2` files with the names `index.html` loads: `Inter-Regular.woff2`,
`Inter-Medium.woff2`, `Inter-SemiBold.woff2`, `Inter-Bold.woff2`, `InterDisplay-SemiBold.woff2`
and `InterDisplay-Bold.woff2`, with the licence as `OFL-Inter.txt`.

The wordmark is Familjen Grotesk Bold (SIL OFL 1.1), already turned into shapes in
`assets/brand/wordmark-forest.svg`, so no font file is needed for it.

## Pictures

The dashboard in the film is a screen recording of one real run of this project's Streamlit app,
recorded frame by frame by `capture/takes.py` and cut into shots by `capture/conform.py`. The
recording is not kept here; `assets/rec/dash-run.json` holds its frame-by-frame log (the time of
each frame, the pointer's path and the page's events) and `capture/run/` holds the run's own files.
The dashboard renders in Streamlit's own Source Sans, as recorded.
