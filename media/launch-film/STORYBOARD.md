# Local AI Orchestrator launch film: storyboard and build

69.9 s (2097 frames), 1920 × 1080, 30 fps. H.264 with AAC at 256 kb/s; measured on the MP4:
-16.1 LUFS integrated, true peak -2.1 dBTP, loudness range 3.4 LU. Made against main @0f3f321.
Every claim in it and its source is in [FACTS.md](FACTS.md); the full brief, shot by shot, is
[SPEC.md](SPEC.md).

## What is real and what is rebuilt

- **Real:** the dashboard and the run in it. One run of `app/streamlit_app.py` on
  `localhost:8501` (run `ui_20261101_230242`, 1 November 2026), with the documented `bootstrap`
  profile, so all ten model calls went to llama3.2:3b. Every number shown from it (8 words, 84,
  216, 360, 0/100, Failed, 3 loops, `word_limit` 3, the per-role table) is the run's own, from
  [capture/run/](capture/run/) and the recorded frames.
- **Recorded frame by frame:** `capture/takes.py` drove headless Chromium at 1280 × 720 and 2x
  density, one screenshot per frame. Typing, clicks and scrolls play at 1x. The model's waiting is
  played faster, and the corner of the window says so: "22× speed" through the supervisor, builder
  and loop 1's judge, "114× speed" through loop 2.
- **Drawn by the film:** the browser window around the recording (with its "localhost:8501"
  pill), the cursor (on the pointer path the take saved; the pointer is not in the screenshots),
  the push-ins, the notes beside the window, the "Code counted 360 words" capsule and the marks on
  the judge's and the fixer's own words.
- **Cut:** at 45.0 s the take jumps past loop 3 to the finished run, and at 47.6 s to Validator
  failures. The scroll it skips holds the "Run saved to:" caption, which shows the working folder's
  path.
- **Not recorded:** the July 2026 run in the opening. It is told with dots, and its numbers
  (about 450 words, 88/100, passed) are from the Phase 6b maintainer audit in `docs/audits/`.
- **Left as recorded:** the Status tile reads "Belo..." (Streamlit cuts "Below threshold"), the
  Run pipeline label is dark on the dark-green button, and "Total runtime: 646.2s" is real but slow:
  five other film builds were running on the machine. The film claims no speed. The fixer's draft,
  references the model invented included, scrolls past at 1x and the camera never stops on it.

## The film

| Time (s) | Scene | Narration | What you see |
|---|---|---|---|
| 0–10.6 | Open | "Ask for a fifty-word summary of why sleep matters. It came back at about four hundred and fifty, and still scored eighty-eight: a pass." | "July 2026 · a test run of this project", "Ask for 50 words." 50 grey dots in a disc, the target ringed in green; more keep arriving until about 450 fill the frame, "about 450 words came back"; a capsule lands: green dot, "88/100 · Passed". The dots draw in to one point. |
| 10.6–19.4 | Lockup | "This is Local AI Orchestrator. Seven local agents, no paid API calls, and one rule: a model can't mark its own homework." | On the music's drop the dial tile grows out of that point and its pointer settles; the wordmark wipes in on "Local". "Seven local agents · deterministic validators · no paid APIs" (the brand sheet's line), then "A model can't mark its own homework." word by word. |
| 19.4–28.2 | Same goal | "Same goal, today. A supervisor sharpens it, and a plain rule picks the fast path." | "The dashboard · a real run", "Same goal, today." The window settles on the real dashboard; the cursor clicks the Task box, the goal types in, Run pipeline. "A plain rule picks the path.": the window steps aside for a note, the supervisor's goal "Summarize the importance of sleep in 50 words.", fast · normal · deep with fast selected, "8 words · 25 or fewer: fast". |
| 28.2–38.8 | The judge | "The builder drafts. The judge, another agent, calls it a pass. Then code counts the words: far too many. The score is forced to zero." | "Loop 1 of 3", "The judge says pass." The builder and judge rows tick; the cursor opens the judge row and its verdict "'total_score': 84, 'pass': True" is marked. "Code counts the words.": the page scrolls to Score progression, 0/100; a note: "loop01_validators.json", "word count 216 is outside the 5-word tolerance for exact target 50", red dot, "Forced to 0", "from 84". |
| 38.8–51.2 | Repair | "The critic and fixer get the exact count and try again. Three loops on, it's still too long, so the run says failed. A small model can miss. It can't claim a pass it didn't earn." | "Loops 2 and 3", "Critic and fixer try again." Loop 2 at 114x; the cursor opens the fixer's row, its claim that the draft "meets the 50-word tolerance for exact target word count" is marked, and under it "Code counted 360 words". "Three loops, still too long.": Run summary, Final score 0/100, Result Failed. "It can't claim a pass it didn't earn.": Validator failures, the dashboard's caption "A high Judge score cannot rescue a draft that violates a checkable constraint" and `word_limit` 3. |
| 51.2–58.2 | Local | "Every call ran locally, on a three-billion-parameter model, with no API keys." | "Metrics summary", "Every call ran locally." The cursor opens Metrics summary (Phase 5); the camera pushes in on the per-role table, llama3.2:3b on every row, and "Total runtime: 646.2s". "On llama3.2:3b, with no API keys." The window lifts away. |
| 58.2–63.5 | Tests | "Two hundred and twenty-seven tests pin it down, the fifty-word bug included." | "pytest · main @0f3f321"; 227 counts up, "tests passed"; "The 50-word bug, as a test": passed, `test_pipeline_fails_when_supervisor_drops_original_word_limit`. |
| 63.5–69.9 | End card | "Local AI Orchestrator. Private multi-agent runs on your Mac." | The dial tile and wordmark, "Private multi-agent runs on your Mac." (the dashboard's own subtitle), github.com/andyyaro/local-ai-orchestrator, held on the track's own ending. |

## Look

- **Style:** a UI film. The frame grammar is the Outbreak Detective films': light frames, a kicker
  over a sentence-case headline, the real product in a browser window rebuilt around the recorded
  clips, a drawn cursor, speed chips, a dot story for the hook and the lockup on the drop. From
  EV-SIENT: push-ins on the element the voice names, the window stepping aside for a short note,
  and a counter that counts.
- **Design system:** HIG Native, as the CERFODES architecture film used it. Ground #F2F2F7, white
  groups with 26 px corners, capsule chips; text #000000 and #68686D. One accent, #1F7A4D, the
  dashboard's own Run pipeline green. Status is always a dot and a word: red #FF383C for "Forced
  to 0" and "Failed", green #34C759 only for the hook's false pass.
- **Brand:** the project's dial (lime #C5D86D on forest #1E2A1A, with a cream #F1EEDC dot) and the
  wordmark, Familjen Grotesk Bold, already outlined. Lime and cream stay inside the tile.
- **Type:** Inter and Inter Display for every word the film sets, standing in for SF Pro, which
  does not load in headless Chromium. No monospace anywhere: code words such as `llama3.2:3b` are
  set in Inter, and the dashboard was recorded with Streamlit's code font set to sans-serif. No em
  dashes, no caps labels and no shadows on screen.
- **Motion:** calm. Headlines rise 22 px out of a light blur on the voice's word times; push-ins are
  slow moves of up to 2x, which the 2x recording keeps sharp; one family of eases.

## Sound

- **Voice:** Kokoro-82M, voice af_heart, speed 1.0, 13 lines. `narration/lines-tts.json` spells
  "AI" and "API" so the voice says them right. Whisper's transcript of every chosen take matches the
  script word for word.
- **Music:** "Nostalgic Night" by Michael Ramir C. (Mixkit 1112), a 68 BPM groove, cut on whole bars
  by `sound/music.py` with 12 ms crossfades:

  | Film (s) | Track | Under |
  |---|---|---|
  | 0–3.5 | bar 17, low-passed at 900 Hz | the hook's first line |
  | 3.5–10.6 | bars 20–21, the breakdown, the low-pass opening | the 450 words and the false pass |
  | 10.6 | bar 22, the drop | "Local": the lockup lands |
  | 10.6–38.8 | bars 22–29 | the lockup, the goal and the judge |
  | 38.8–52.9 | bars 12–15, the fullest phrase | the repair loops and "failed" |
  | 52.9–63.5 | bars 30–32 | "locally" and the tests |
  | 63.5–69.9 | bars 33–34, the track's own ending | the end card; the last stab lands after "Mac" |

- **Effects:** 105 soft Mixkit sounds in one vocabulary: a pop when a part arrives, a tick for a step
  or a counter, an air whoosh when the window moves, a low pop only when code overrules a model (the
  forced zero and Failed), a riser and a soft hit into the drop, a lower click on each recorded
  pointer press and single key taps under the typed goal. `sound/cues.py` reads their times from
  the composition itself. The list is in [assets/audio/SOURCE.md](assets/audio/SOURCE.md).
- **Levels** (`sound/mix.py`): speech -15.3 LUFS; the music 8.8 dB under the voice between lines and
  13.4 dB under while it speaks; each effect peaks one frame after its picture, 3 to 6 dB over the
  music there and at least 6.5 dB under the voice. Master -16.0 LUFS and -2.0 dBTP in the mix,
  -16.1 LUFS and -2.1 dBTP in the MP4.

## Build

Get the inputs first: `tools/fetch_vendor.sh` for GSAP, then the fonts, music and effects listed
in [assets/audio/SOURCE.md](assets/audio/SOURCE.md). The Python steps need numpy, soundfile,
scipy, librosa and mlx-whisper (`<voice-venv>`), or Playwright with Chromium (`<pw-venv>`).

```sh
tools/fetch_vendor.sh
# Voice each line of narration/lines-tts.json with Kokoro-82M (af_heart) at speeds 1.0 and 1.06,
# as narration/takes/<id>.<k>.wav
<voice-venv>/bin/python -I narration/pick.py takes       # best take per line, words.json
<voice-venv>/bin/python -I sound/music.py                 # assets/audio/music.wav, sound/grid.json
<voice-venv>/bin/python -I sound/mix.py                   # assets/vo.js, assets/timing.js, a first mix

# The take, only to record it again: a real model run of about ten minutes. Needs Ollama with
# llama3.2:3b, and a clone of this repository in work/repo (active_profile: bootstrap in
# config/models.yaml, a fresh runs/) with its venv in work/venv.
python3 -I capture/serve.py start
<pw-venv>/bin/python -I capture/takes.py                  # assets/rec/dash-run.mp4 and .json, capture/run/
python3 -I capture/serve.py stop
python3 -I capture/conform.py                             # assets/shots/*.mp4, assets/edit.js, assets/edit.json

python3 -I build.py                                       # scene and clip windows into index.html
<pw-venv>/bin/python -I sound/cues.py                     # the picture's effect cues, sound/sfx-cues.json
<voice-venv>/bin/python -I sound/mix.py                   # the final mix with the effects
npx --yes hyperframes@0.8.173 lint && npx --yes hyperframes@0.8.173 check --json
npx --yes hyperframes@0.8.173 render -o renders/raw.mp4 --fps 30
ffmpeg -y -i renders/raw.mp4 -i assets/audio/mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k \
  -shortest -movflags +faststart renders/local-ai-orchestrator-v1.mp4
python3 -I narration/vtt.py                               # renders/local-ai-orchestrator-v1.en.vtt
```

Without the screen recording, `capture/conform.py` cannot cut new shots; the edit it wrote is kept
in `assets/edit.js`. The scenes find their cue words by text in `window.VO` and the window reads
the take's marks from `window.EDIT`, so a new take or a re-voiced line re-times the picture; run
`sound/cues.py` and `sound/mix.py` again after it so the effects follow. The last ffmpeg step puts
the exact mix back on the picture, because the renderer's own audio comes out quieter.

## The README preview

`docs/assets/readme/local-ai-orchestrator-in-action.webp` is 22.0–38.0 s of the film: the goal typed
into the real dashboard, Run pipeline, the fast-path note, the judge's 84 and pass, and the score
forced to 0. 1200 × 676, 15 fps, lossy quality 90, 2.3 MB. The film's light frames need no denoise.

```sh
mkdir -p preview
ffmpeg -ss 22.0 -t 16 -i renders/local-ai-orchestrator-v1.mp4 \
  -vf "fps=15,scale=1200:676:flags=lanczos" preview/f%03d.png
img2webp -loop 0 -lossy -q 90 -m 6 -d 67 preview/f*.png \
  -o ../../docs/assets/readme/local-ai-orchestrator-in-action.webp
```
