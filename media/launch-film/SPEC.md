# Local AI Orchestrator launch film: SPEC

```text
GOAL:    a developer understands, in about a minute, what Local AI Orchestrator is (seven local agents on Ollama,
         no paid APIs) and the one thing that sets it apart: a model cannot mark its own homework. The film shows
         it on a REAL run in the real Streamlit dashboard: the judge model calls a too-long draft a pass, plain code
         counts the words and forces the score to zero, the repair loop tries again, and the run reports what really
         happened. Proof: 227 tests (pytest, main @0f3f321).
OUTPUT:  HyperFrames 0.8.173, 1920 x 1080, 30 fps, 69.9 s = 2097 frames (set by the sound stage, sound/timing.json).
         renders/local-ai-orchestrator-v1.mp4.
SOUND:   (sound stage, 2026-11-01) "Nostalgic Night" (Michael Ramir C., Mixkit 1112, Mixkit Stock Music Free License).
         GRID (librosa beat track, checked on kick/snare onset peaks: residual 6 ms, drift 3 ms per 100 s; attacks
         measured on the waveform): a 68 BPM backbeat (kick on 1 and 3, snare on 2 and 4; librosa reads 136
         double-time), quarter 0.8823 s, bar 3.529392 s; track bar n starts at 0.436 + 3.529392 n s. The harmony is a
         two-bar cycle (even bars G/Bb, odd bars D/A), so every join goes from an odd bar to an even bar.
         STRUCTURE: drums from the top in four-bar phrases (12-15 the fullest); the breakdown is bars 20-21 (71.0-78.1 s:
         the low-mids drop out, the kick drops out for half of bar 21, a near-silent gap before the re-entry); the
         groove re-enters on bar 22 (78.08 s); bar 34 is the track's ending (last stab 121.77 s, silent by about 123 s).
         THE CUT (sound/music.py -> assets/audio/music.wav, sound/grid.json), film seconds, 12 ms crossfades on bar lines:
           0-3.529       bar 17, low-passed at 900 Hz (zero phase), under the hook's first line
           3.529-10.588  the breakdown (bars 20-21); the low-pass opens until the build is full at the drop
           10.588        THE DROP (bar 22) on "Local" (v03's "Local" at 10.61): the lockup lands
           10.588-38.823 bars 22-29, the groove under the lockup, the goal and the judge
           38.823-52.941 bars 12-15, the fullest phrase, under the repair loops and "failed" (bar 15's fill leads into s6)
           52.941-63.529 bars 30-32, settled again under "locally" and the tests
           63.529-69.9   bars 33-34, the end card on the track's own ending; the last stab at 68.39 lands after "Mac"
                         (67.53); the film ends after the ring-out.
         Film bar lines: k x 3.529392 s (grid.json film_bars / film_half_bars) for cuts and titles on the beat.
         VOICE: Kokoro af_heart, speed 1.0 takes (narration/chosen). lines-tts.json spells "AI" and "API" plainly
         ("A P I" in v04 was heard as "pay-to-PI"; v11 keeps "A P I", heard right). pick.py's whisper transcript of
         every chosen line matches the script word for word. Slots (film s, sound/mix.py SLOTS):
           v01 0.70-3.63   v02 4.25-8.82   v03 10.25-12.07  v04 12.65-18.58  v05 21.00-25.85  v06 28.75-32.34
           v07 33.05-37.17 v08 39.25-42.30 v09 43.70-46.88  v10 47.35-50.75  v11 51.75-56.88  v12 58.65-62.94
           v13 63.95-67.94
         assets/vo.js (window.VO) has every word's film time. Whisper writes numbers as digits, so the cue words are
         "50" (then "-word"), "450", "88", "3", "227", e.g. W("v02", "88"); "multi" then "-agent" in v13.
         LEVELS (sound/mix.py, measured on the final stems): speech -15.3 LUFS; the bed 8.8 dB under the voice between
         lines and 13.4 dB under while she speaks (ducked 4.6 dB, 40 ms attack, 450 ms release); master -16.1 LUFS
         integrated, true peak -2.0 dBTP (-16.1 LUFS / -2.1 dBTP after AAC 256k). Fixed from secure-data-hub's mix.py:
         the voice is measured in stereo as it plays (the mono file read 3 dB low) and without a talk-time correction
         (R128 gating already drops the silences); the limiter ceiling is 0.74 (0.79 gave -1.46 dBTP).
         EFFECTS (finish stage, 2026-11-02): 105 effects, placed by sound/mix.py sfx_events from the picture's own cues
         (sound/cues.py -> sound/sfx-cues.json from window.__SFX) and the title scenes' word times. Each peaks one frame
         after its picture; its loudest 100 ms (K-weighted) is set 3-6 dB over the bed's 400 ms loudness there and at
         least 6.5 dB under the line being spoken (report_effects() prints all of them; one press, 52.03, is held under
         the voice over bar 15's fill). Vocabulary: pop (2357) a part arriving; tick (1120) a row done, a line part, a
         mark, the 50 -> 450 and 0 -> 227 counts; air whoosh (1492) the window settling, stepping aside and back, the
         swap, the exit; low pop (2357 at 0.78) the forced zero and Failed; windy swoosh (1465) + riser (2408) + soft
         hit (3005 at 0.9) into the drop; the pointer's 5 presses (1120 at 0.86); 45 single key taps (2538, sliced)
         under the typed goal. Camera push-ins are silent (calm). The "22× speed" chip is silent (it lands 17 ms after
         the Run pipeline press); the claim mark at 43.13 is silent (the chip lands 0.2 s later).
         EFFECTS before the finish stage (sound stage): the drop (a swell into it, a soft pop as the tile lands) and the end card (a soft
         pop as the lockup lands at 63.78, a tick on "Private" at 65.51). The finish stage adds the rest from
         sound/sfx-src (Mixkit, copied from secure-data-hub) in ONE vocabulary: a soft tick when an agent row
         completes; a soft pop when a note or chip arrives; a low muted thud only when code overrules a model (the
         forced zero, the "Failed" result); a light whoosh on window moves; soft clicks on cursor presses; quiet key
         taps under the typed goal; a gentle rising tick run under the 227 counter.
LOOK:    THE DESIGN SYSTEM IS HIG NATIVE (Andy's request: the CERFODES architecture film, cerfodes-architecture-en-
         1080p.mp4, used it too; the "HIG Native" design system, read in research). Taken from it, as the CERFODES
         film applied it:
           ground    grouped-background-primary #F2F2F7; groups/cards background-primary #FFFFFF at radius-group 26 px;
                     small tiles radius-thumbnail 10 px; controls and chips are capsules (radius 9999 px); concentric
                     corners (inner radius = outer minus inset).
           text      label-primary #000000; label-secondary #68686D (CERFODES' video-legible solid, >= 4.5:1);
                     separator rgba(0,0,0,0.12); fills rgba(120,120,128,0.16 / 0.12 / 0.08).
           status    always a dot AND a word, never colour alone: system-red #FF383C "Forced to 0" / "Failed" (3.6:1: dots and 28 px+ Semibold words only);
                     system-green #34C759 dot with a label-primary "Passed" (the hook's false pass only).
           accent    ONE accent: #1F7A4D, the dashboard's own --green (its Run pipeline button), for kickers and the
                     selected segment. 4.77:1 on #F2F2F7, 5.32:1 on white.
           type      the system face, as CERFODES: @font-face "HostUI" from local("SF Pro"), local("SF Pro Display"),
                     local(".SF NS") (a bare -apple-system is swapped for Inter at render time). Headlines 72-80 px
                     Semibold, tracking about -0.02em; kicker 28 px Semibold in the accent; body/notes 34-36 px Regular
                     and Semibold; chips 26-28 px Semibold; numbers with font-variant-numeric: tabular-nums. Sentence
                     case everywhere: NO caps labels in this film (so rule 3's Montserrat is not needed). NO MONOSPACE:
                     code words (word_limit, llama3.2:3b, localhost:8501) are set in HostUI.
           shadows   none on content (HIG and Andy agree). The window gets a 1.5 px hairline, no shadow.
         Brand (docs/assets/brand, copied to assets/brand/): the mark is a dial (lime #C5D86D disc, a dark pointer, two
         45%-lime dots and one cream #F1EEDC dot) on the forest ground #1E2A1A; wordmark "local-ai-orchestrator",
         Familjen Grotesk Bold, already outlined in the SVGs. On the light film: icon-rounded.svg (the dark tile with
         the lime dial) beside the wordmark from lockup-black.svg recoloured #1E2A1A. Lime and cream live inside the
         tile only (lime fails contrast on light).
         REFERENCE FILMS. Base: the Outbreak Detective films (intro v7 + share v7): one light look; kicker over a bold
         sentence-case headline at the top left; the real product recorded and shown in HyperFrames'
         browser-device-stage window rebuilt around media clips (settle 0.9 s: opacity over 66%, rise 4.5% of frame
         height, scale 0.965 -> 1, power ease-out; screen swap 0.55 s through the bare stage; "up" exit 0.5 s
         power2.in); the cursor drawn by the composition on the recorded mouse path; a take shown faster than real
         time says so in its corner ("16x speed", HostUI, not mono); a dot story for the hook; the lockup on the drop;
         an end card of logo, one line and the URL. Changed from Outbreak: the address pill is HostUI (Outbreak's is
         SF Mono: banned), no window shadow, ground #F2F2F7. From EV-SIENT: push-ins on the exact element the voice
         names, values landing on their words, the window stepping aside for a short note, a counter that counts.
MOTION:  calm. Headlines rise 22 px with blur 5 -> 0 on the voice's word times (window.VO via the W() cue helper);
         exits blur out at about half the entrance. Push-ins are slow EIO moves about the element's own centre, up to
         2x (the takes are recorded at 2x pixel density, so they stay sharp). Notes arrive as white groups (radius 26)
         that rise 16 px and fade in; the window slides 300-360 px left to make room and returns. One ease family:
         EO arrivals, EI exits, EIO moves at rest-to-rest. Cuts and titles on beats (0.8824 s) where the voice allows.
         No idle motion, no screen shake, no flood of elements.
SHOTS:   (windows from sound/timing.json, on the track's bar and half-bar lines; build.py writes them into index.html.
         Cue words in film seconds from assets/vo.js.)
         s1 open     0-10.588  Kicker "July 2026 · a test run of this project", headline "Ask for 50 words." 50 grey
                              dots in a phyllotaxis disc; on v02 dots keep arriving (the target 50 ringed in the accent)
                              until about 450 fill the frame calmly, counter "about 450 words"; a capsule lands on
                              "eighty-eight": green dot + "88/100 · Passed". The dots draw in to the dial's centre.
                              Cues: "50" 1.26, "450" 5.17, "88" 7.21, "pass" 8.25; the crash at 3.53 (bar 20).
         s2 lockup   10.588-19.412  On the drop the dial tile lands (its pointer settles from the left dot through the top
                              dot to the cream dot, the real mark's pose), the wordmark wipes in beside it. v04: line 1
                              "Seven local agents · deterministic validators · no paid APIs" (the brand sheet's own
                              line), then "A model can't mark its own homework." (README) lands on "homework".
                              Cues: drop 10.588, "Local" 10.61, "Seven" 12.65, "homework" 18.05.
         s3 goal     19.412-28.235  Kicker "Same goal, today", headline "A plain rule picks the path." The window
                              settles with the real dashboard (address pill "localhost:8501"). The cursor clicks the
                              Task box, the goal types in (1x), the cursor presses Run pipeline; "supervisor" ticks
                              (sped up, chip). The window steps left; note: a HIG segmented control "fast | normal |
                              deep" with "fast" selected in the accent on "fast path", and one line under it: "25 words
                              or fewer: fast" plus the take's refined-goal word count ("Refined goal: N words").
                              Cues: window settles 19.41-20.31; typing about 20.6-22.6 (v05 "Same goal, today"
                              21.00-21.9 runs over it); "supervisor" 22.58 (Run pressed just before); "fast" 25.20.
         s4 judge    28.235-38.823  Headline "The judge says pass." builder ticks, "Loop 1 of 3", judge ticks; the cursor
                              opens the judge row; push-in on its own words "'total_score': 84, 'pass': True" (the take's) on "pass".
                              v07: headline becomes "Code counts the words."; push to the Score progression panel,
                              "Current score 0/100 · Below threshold" lands on "zero"; the window steps left for a
                              note: red dot + "Forced to 0", and the run's own validator line in quotes, in the take "word
                              count 216 is outside the 5-word tolerance for exact target 50", source caption
                              "loop01_validators.json".
                              Cues: "builder" 28.89, "judge" 30.15, "pass" 31.87, "counts" 33.55, "far" 34.47 (the
                              validator line can land here, 4 s to read), "zero" 36.69 ("Forced to 0").
         s5 repair   38.823-51.176  "Loop 2 of 3": critic, fixer, judge tick at speed (chip). If the take's fixer or
                              judge claims the limit was met (trial 1: "meets the 50-word limit exactly"), one push-in
                              on that sentence, then the note "word count 360" from loop02_validators.json (the take: the loop 2 fixer
                              wrote it "meets the 50-word tolerance for exact target word count"). "Loop 3 of
                              3". The window scrolls (real wheel) to Run summary: push on "Final score 0/100" and
                              "Result: Failed" on "failed" (low thud). v10: push on the dashboard's own caption "A high
                              Judge score cannot rescue a draft that violates a checkable constraint" and the Validator
                              failures row "word_limit · 3".
                              Cues: "critic" 39.39, "try again" 41.61; the fixer's claim and "word count 294" in
                              the voice gap 42.30-43.70; "Three loops" 43.70, "failed" 46.38; "miss" 48.39, "pass"
                              49.77, "earn" 50.37. Bar 15's fill (49.4-52.9) leads into s6.
         s6 local    51.176-58.235  The cursor opens "Metrics summary (Phase 5)"; push-in on the per-role table: every
                              row's model "llama3.2:3b", calls, elapsed_ms; "Total runtime: N s" (the take's). The
                              window lifts away ("up" exit).
                              Cues: "Every call" 51.75, "locally" 52.59, "3 billion" 53.55, "API keys" 55.71-56.88.
         s7 tests    58.235-63.529  On the ground: "227" counts up (tabular figures), "tests passed" beside it; under it
                              one line in HostUI: "test_pipeline_fails_when_supervisor_drops_original_word_limit" and
                              "pytest · main @0f3f321".
                              Cues: "Two hundred and twenty-seven" 58.65 (the count runs), "tests" 59.99 (it lands),
                              "50-word bug" 61.57.
         s8 end      63.529-69.9  The dial tile and wordmark (centred lockup), the line "Private multi-agent runs on
                              your Mac." (the dashboard's own subtitle), the URL github.com/andyyaro/local-ai-
                              orchestrator in the accent. Hold on the track's ending.
                              Cues: "Local" 63.95, "Private" 65.51, "Mac" 67.53, the last stab 68.39, silence 69.0.
         Variant B (only if the film's take actually passes in loop 2 or 3): v09 becomes "On the next loop it lands
         inside the limit, and passes." and v10 "If it hadn't, the run would say so."; s5 pushes on "Result: Passed".
         Never stage or fake either outcome. Variant B is pre-voiced (narration/lines-variant-b.json; takes v09b/v10b
         in narration/takes, transcripts verified): to use it, put the texts in lines.json v09/v10, copy the takes to
         v09.N/v10.N, re-run pick.py and set v10's slot to about 47.8 (v09b is 0.4 s longer than v09).
CAPTURE: The real dashboard, app/streamlit_app.py from andyyaro/local-ai-orchestrator main @0f3f321, cloned in the
         scratch dir (venv there: Python 3.12, requirements.txt with requirements-lock.txt constraints; Streamlit
         1.58.0). Facts learned in research (all verified headless):
         - Run it as: streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
           --server.headless true --browser.gatherUsageStats false --server.fileWatcherType none
           --theme.codeFont "sans-serif". Port 8501 is the README's address, so the pill is true. --theme.codeFont is
           Streamlit's own config flag; without it the inline code ("bootstrap" profile, "fast") renders in Source Code
           Pro (mono). Before recording, probe every visible text node's computed font-family (tools/shoot.py does)
           and fail on any monospace.
         - Model: set active_profile: bootstrap in the clone's config/models.yaml (the documented switch; every role
           on llama3.2:3b, 2.0 GB). The sidebar cannot be opened in this Streamlit version (the app's CSS hides
           stToolbar, which holds the expand button), so the model and path overrides are out of reach; the default
           Path is auto and the sliders default to 3 loops, threshold 70. Restart Streamlit after editing the YAML
           (config is cached).
         - Goal: "Write a 50-word summary of why sleep matters." (the audit's goal and the regression test's).
           Router: the refined goal (trial: 16 words) is <= 25 words, so path "fast": planner skipped, a judge pass,
           then the repair loop (critic, fixer, judge) because the word-limit failure is repairable.
         - Trial run (research, 2026-11-01, ui_20261101_212423, archived in the scratch dir trial-artifacts/):
           supervisor 27 s, builder 37 s (193 words), judge 87 -> forced 0; loop 2 fixer 294 words, judge 82 ->
           0; loop 3 299 words, judge 89 -> 0; synthesizer 144 words -> reverted to the best draft;
           Result Failed, stop reason hard_fail: ['constraint_violation'], total runtime 510.9 s, 10 calls, all
           llama3.2:3b. The fixer and the judge both wrote that the draft "meets the 50-word limit exactly".
         - A second trial died at the builder: "Ollama timed out after 120s on model 'llama3.2:3b'" with the machine at
           load average 95. Record when the load is lower (check uptime; warm the model with one short call first);
           if a take errors, discard it and record again. One model, one run at a time; ollama stop llama3.2:3b and
           stop Streamlit afterwards.
         - Record in real time (the backend's model time cannot run on a virtual clock): viewport 1280 x 720 CSS px at
           device scale 2, so the 720-880 px content column fills the window and push-ins stay sharp. The page does
           not auto-scroll: follow the run with the real wheel over the column. Save frames as JPEG, at full rate only
           around interactions and at a low rate through model waits; delete raw frames once encoded. Every sped-up
           stretch carries its factor in the window corner. Typing and clicks play at 1x.
         - Avoid in frame: the "Run saved to:" caption (it shows the scratch path); the model's invented statistics
           inside builder/fixer text (e.g. "a 2015 meta-analysis") are never pushed in on or presented as facts;
           the "Open run details" selectbox (it reruns the page and clears the run).
         - Read only: no form other than the dashboard's own goal box, nothing personal, nothing uploaded. The film's
           run history is a fresh runs/ in the scratch clone, not Andy's own runs/history.db.
TAKE:    (capture stage, 2026-11-01) ONE take, assets/rec/dash-run.mp4 + .json (2269 frames, 2560 x 1440 = the 1280 x 720
         viewport at 2x; one video frame per captured frame, NOT real time: the JSON gives each frame's wall clock, take time,
         mode i/w, pointer x/y in CSS px and pressed; marks; page events), recorded by capture/takes.py (capture/rec.py:
         i frames = 1/30 s of pointer/typing/scroll with the page's animations slowed to match; w frames = real time while the
         model works). Run ui_20261101_230242 (capture/run/): refined goal 8 words, fast path; builder 216 words; loop 1 judge
         row 'total_score': 84, 'pass': True; forced 0; loop 2 fixer 360 words and its claim "meets the 50-word tolerance for
         exact target word count"; loop 3 401 words; synthesizer reverted; Final score 0/100, Result Failed, Loops 3, Mode
         writing; 10 calls, all llama3.2:3b; Total runtime 646.2s. The narration fits as voiced (no re-voice, no Variant B).
         THE EDIT: capture/conform.py + capture/shotlist.py -> assets/shots/{goal,judge,repair,local}.mp4 (2560 x 1440, 30 fps,
         yuvj420p full range BT.601 tagged like the Outbreak takes, keyframe every 10 frames) and assets/edit.js (window.EDIT;
         slim copy assets/edit.json): per shot start/dur (film s), the take frame per film frame, the cursor per film frame
         ([x, y, pressed] in CSS px of 1280 x 720; outside 0..1280/0..720 = off the window, do not draw), speed stretches
         with the label to show, in-shot cuts, marks (clicks, keys, rows completing) and rects for push-ins, in film seconds.
           goal    19.400-28.233  idle dashboard as the window settles; pointer enters 19.45, clicks Task 20.23, types 20.43-
                                  22.23 (1x), presses Run pipeline 22.93; the supervisor row appears 23.07 and ticks 25.70;
                                  builder running. Sped 22.95-28.235 "22× speed" (21.7x).
           judge   28.233-38.833  builder ticks 28.70, Loop 1, judge ticks 30.13 ("22× speed" to 30.42); pointer clicks the
                                  judge row 31.17 (1x), verdict open from 31.79 ("'total_score': 84, 'pass': True",
                                  rects.judge1_open_text [787, 591.5, 188, 21]); held to 33.33; page scrolls (1x) to Score
                                  progression, "0/100" in view from 34.77 (rects.score_current); held.
           repair  38.833-51.167  loop 2 at "114× speed" 38.82-40.73 (critic ticks 39.33, fixer 40.20, judge 40.60, Loop 3
                                  appears 40.73); pointer opens the loop 2 fixer row 41.43 (1x), the page scrolls to its last
                                  paragraph: the claim in view 42.79-45.00 (rects.claim_meets [655, 423, 302, 24] = "meets the
                                  50-word tolerance for exact target word count."; model-invented references sit above it:
                                  keep the push-in on the claim). CUT 45.000 (beat) past loop 3 to the finished run: 1x scroll
                                  to Run summary landing 46.40 on "failed" (rects.final_score, rects.result; the frame's bottom
                                  edge cuts the "Stop reason" caption and the dashboard's Download button renders as a black
                                  pill with an unreadable label: frame the push-in on the four tiles). CUT 47.633 (beat) to
                                  Validator failures (rects.vf_caption, rects.vf_table: "word_limit", 3). The skipped scroll is
                                  where the "Run saved to:" caption (the scratch path) is: never shown.
           local   51.167-58.233  pointer opens "Metrics summary (Phase 5)" 52.03 (1x); scroll to the per-role table and
                                  "Total runtime: 646.2s" in view from 54.13 (rects.role_table, rects.runtime); held to the end.
         The composition adds the window, the cursor, the push-ins, the notes and the speed chip from window.EDIT; it must
         not show a sped stretch without its label. Re-cut: python3 -I capture/conform.py (no re-take needed).
BUILD:   (build stage, 2026-11-02) index.html + compositions/s1-open ... s8-end.html, assets/cues.js (window.FILM: WA()
         word-time lookup, the Outbreak eases, CUE times), build.py (writes the scene windows from sound/timing.json AND
         each <video id="v-goal|judge|repair|local"> data-start/data-duration from assets/edit.json).
           type      Inter / Inter Display (OFL, assets/fonts/OFL-Inter.txt; Outbreak's own SF stand-in) as "FilmText" and
                     "FilmDisplay". local("SF Pro") does not load in HyperFrames' headless Chromium (font status "error";
                     the CERFODES film's own state logged "Fonts failed: HostUI"), so HostUI would fall back silently.
           window    browser-device-stage 1283 x 779 at (318.5, 252), 56 px bar, "localhost:8501" capsule, 1.5 px separator
                     border, radius 24, no shadow; Outbreak's settle/"up" exit; steps aside (x -360, scale 0.72; review: was
                     -390) for the s3 and s4 notes, which sit at x 1142 so window and note are centred (138 px margins, 80 px
                     gap); a note arrives only 0.45 s into the step, once the window has cleared its place. Shots placed in index.html as frame-accurate clips; per-frame camera (xf clamp, log-scale
                     zoom) and the drawn cursor from EDIT frames; speed chip on every sped stretch (22x, 114x).
           changes   s5's note became an in-window capsule "Code counted 360 words" under the fixer's claim (ring on
                     "meets the 50-word tolerance for exact target word count."); s5 kickers follow the dashboard section
                     (Loops 2 and 3, Run summary, Validator failures). Push-ins keep the Download pill, the "Stop reason"
                     caption and the "Run saved to:" path out of frame; the s4 push still shows the Status tile's
                     Streamlit truncation "Belo..." beside 0/100 (the take's own UI).
           review    (2026-11-02, REVIEW.md) the two phrases inside running text (the judge's "'total_score': 84, 'pass': True,"
                     and the fixer's "meets the 50-word tolerance ...") are marked with a borderless selection-like fill
                     (.ring.mark) measured edge to edge from the take's pixels, because the 5 px word gaps left no room for
                     a bordered ring; the caption ring is cut to the caption's own width; the s6 push and the model-column
                     ring land on "model"; note quotes use text-wrap: balance (no orphan "50”").
           sound     window.__SFX lists every placed event (clicks, keys, ticks, whoosh, pops, thuds, rings, counter,
                     drop, lockup) for the finish stage. No render made in this stage.
OBJECTS: real things only: the dashboard (title "Local AI Orchestrator", subtitle "Private multi-agent runs on your
         Mac.", Task box, Run pipeline, Progress rows supervisor/builder/critic/fixer/judge/synthesizer, "Loop n of
         3" cards, Score progression, Final output, Run summary with Final score / Result / Loops / Mode, Validator
         failures with its caption, Metrics summary (Phase 5)); the take's run folder (00_supervisor.json,
         loopNN_validators.json, loopNN_judge.json, run_summary.json); orchestrator/router.py (FAST_PATH_WORD_
         THRESHOLD = 25, deep for coding/debugging and keywords); orchestrator/validators.py (count_words,
         EXACT_TOLERANCE_FRACTION 0.10, apply_validator_results_to_verdict -> pass False, total_score 0); the
         phase 6b audit (the July 2026 run: about 450 words, 88/100, passed: true); the regression test
         tests/test_pipeline_routing.py::test_pipeline_fails_when_supervisor_drops_original_word_limit; pytest 227
         passed (main @0f3f321, also at v2.0.0); the brand files. Numbers shown from a take must be that take's.
BANNED:  monospace anywhere (Outbreak's mono address pill, HIG Native's --font-mono, Streamlit's Source Code Pro);
         em dashes and en-dash separators on screen; caps labels in any face but Montserrat (none planned); the Huly
         look; Orkestra v2's dark Linear look; Provalume's Biennale paper; drop shadows on content and on the window;
         three feature cards in a row; the logo docked in a corner; a busy architecture diagram (the README's
         mermaid chart is NOT redrawn); screen shake; floods of messages; any staged, mocked or re-typed model
         output; "open source"/"MIT" claims (the repo has no LICENSE file); hype words.
QA:      snapshots at 2.0, 6.0, 9.6, 11.5, 16.5, 18.6, 21.5, 25.6, 30.0, 32.2, 37.2, 40.5, 43.0, 46.6, 50.2, 53.8,
         56.5, 60.2, 62.6, 65.8, 69.0 (from the sound stage's windows and cue words; re-check after the finish). At each: no mono (grep the project for
         mono|Mono|monospace|Courier|Menlo|Consolas|ui-monospace and probe computed fonts), no em/en dashes, no
         shadow, every number traceable in FACTS.md, the speed chip present on every sped-up take, text >= 24 px
         except the browser's own recorded UI. lint and check: 0 errors, 0 warnings. Loudness -16 LUFS +-0.5,
         true peak <= -1.5 dBTP.
```

## Plumbing

Copy from secure-data-hub (never edit it): build.py, index.html (scene hosts, the W() cue helper reading
window.VO), compositions/*.html pattern (template, #root, a paused GSAP timeline on window.__timelines[id]),
narration/pick.py, sound/music.py, sound/mix.py, sound/sfx-src/, assets/vendor/gsap.min.js, hyperframes.json,
package.json. Take the window/cursor/speed-chip pattern from the outbreak-detective share film (share-film/src/film.html,
read only), minus its shadow and mono pill. The narration must be voiced AFTER the film's take is recorded and its
numbers checked against FACTS.md (v06-v11 describe the take).

Sound stage (2026-11-01): narration/pick.py, sound/music.py, sound/mix.py, sound/sfx-src/ and build.py are copied and
adapted (pick.py's norm() for "AI", "API" and whisper's digits, and a pin for a late first word; music.py cut for this
track; mix.py's slots, 8 scene windows, level fixes and level report; build.py's hosts s1-open, s2-lockup, s3-goal,
s4-judge, s5-repair, s6-local, s7-tests, s8-end). The orchestrator ran the sound stage before the capture stage, so the
voice was made from the research script: v05-v11 describe the research trial (judge pass then forced 0, three loops,
Result Failed, every call on llama3.2:3b). The capture stage must check its take against them; if the take passes in
loop 2 or 3, switch to Variant B (pre-voiced, see SHOTS); if the take's run differs in any other way, re-voice the
line. Only the wording is fixed now; no take numbers are spoken.

Rebuild the sound:

```sh
# voice each line of narration/lines-tts.json with Kokoro-82M (af_heart) at speeds 1.0 and 1.06, as narration/takes/<id>.<k>.wav
python3 -I narration/pick.py takes                                  # chosen/<id>.wav + words.json
python3 -I sound/music.py                                           # assets/audio/music.wav, sound/grid.json
python3 -I sound/mix.py                                             # mix.wav, vo.wav, vo.js, timing.js, timing.json
python3 -I build.py                                                 # scene windows into index.html (once it exists)
```
