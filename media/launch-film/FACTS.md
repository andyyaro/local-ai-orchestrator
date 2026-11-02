# Local AI Orchestrator film: FACTS

Every claim on screen or in the narration, its source, and the value checked on 2026-11-01 (research stage).
Repo: github.com/andyyaro/local-ai-orchestrator, cloned at main @0f3f321 (0f3f32128c302ff4709297b58faac50957557f6e,
2026-11-01 10:57 -0500, "Add project logo"); release v2.0.0 = 2912398 (2026-07-04), published 2026-07-05.
Paths below are repo paths unless they start with "scratch:" (the research working folder, not kept here).

## Narration

| Id | Claim | Source | Verified value |
|---|---|---|---|
| v01 | the goal "a fifty-word summary of why sleep matters" | docs/audits/2026-07-04-phase-6b-maintainer-report.md ("Write a 50-word summary of why sleep matters."); scripts/local_acceptance.sh | exact goal text |
| v02 | "about four hundred and fifty", "scored eighty-eight: a pass" | same audit: run runs/20260704_171324/ "produced a ~450-word essay with citations, yet the run reported score 88/100, passed: true" | ~450 words; 88/100; passed: true (a real run, July 4, 2026, before the fix) |
| v03, v13 | the name "Local AI Orchestrator" | README.md title; app/streamlit_app.py page title and hero h1 | "Local AI Orchestrator" (the wordmark spells it local-ai-orchestrator) |
| v04 | "seven local agents" | agents/ (supervisor, planner, builder, critic, fixer, judge, synthesizer); README "7-agent quality pipeline" | 7 agent classes |
| v04 | "no paid API calls" | README Features: "Fully local by default: No API keys, no subscription, no paid model calls"; config/models.yaml provider: ollama, cloud.enabled: false; orchestrator/adapters.py AnthropicAdapter raises NotImplementedError | true by default |
| v04 | "a model can't mark its own homework" | README, Architecture: "A model cannot mark its own homework." | verbatim idea, contracted |
| v05 | "same goal, today" | the film's take (scratch: trial-artifacts/ui_20261101_212423 in research) | TAKE: the goal typed in the dashboard's Task box (capture/run/run_summary.json goal) |
| v05 | "a supervisor sharpens it" | agents/supervisor.py (returns refined_goal and mode); take's 00_supervisor.json | TAKE: "Summarize the importance of sleep in 50 words.", mode writing. Research trial: "Explain the importance of sleep in maintaining physical and mental health, within a 50-word limit." mode writing |
| v05 | "a plain rule picks the fast path" | orchestrator/router.py classify_path: no model call; FAST_PATH_WORD_THRESHOLD = 25; coding/debugging and keywords ("comprehensive", "step by step", "edge cases" ...) go deep; else normal. config/models.yaml paths.fast: skip_planner, skip_critic_fixer_loop | TAKE: refined goal 8 words -> path "fast" (run_summary.json, pipeline.log). Research trial: refined goal 16 words -> path "fast" (run_summary.json "path": "fast"; dashboard "Path selected: fast") |
| v06 | "the judge, another agent, calls it a pass" | the take's judge row text (on_step output is the verdict before the validator runs) | TAKE loop 1: 'total_score': 84, 'pass': True (22+20+24+18). (Research trial: 87) |
| v07 | "code counts the words" | orchestrator/validators.py count_words (whitespace split), extract_word_limit (regex, no model), check_word_limit; exact mode tolerance EXACT_TOLERANCE_FRACTION 0.10 -> 5 words for 50 | TAKE loop01_validators.json: "word count 216 is outside the 5-word tolerance for exact target 50" (research trial: 193) |
| v07 | "the score is forced to zero" | validators.py apply_validator_results_to_verdict: pass False, total_score min(score, 0), hard_fails + constraint_violation | TAKE: loop01_validators.json "word count 216 ..."; score 0, dashboard "Current score 0/100". Research trial: score 0, dashboard "Current score 0/100", "Below threshold" |
| v08 | "the critic and fixer get the exact count and try again" | run.py _run_critic_fixer_judge_iteration appends "DETERMINISTIC CONSTRAINT FEEDBACK FROM PREVIOUS REVISION: <detail> The next revision MUST satisfy this constraint exactly"; fast path falls back to Critic/Fixer on a repairable validator failure (should_break_on_hard_fail) | trial: loops 2 and 3 ran critic, fixer, judge |
| v09 | "three loops on, it's still too long, so the run says failed" | the take's run_summary.json and dashboard Run summary | TAKE: 360 and 401 words (loop02/03_validators.json), scores [0, 0, 0], Result "Failed", Loops 3. Research trial: 294 and 299 words (loop02/03_validators.json), scores [0, 0, 0], Result "Failed", stop reason hard_fail: ['constraint_violation'] |
| v10 | "a small model can miss" | v2.0.0 release notes, Known limitations: "Strict exact-word-count compliance remains difficult for small local models."; docs/audits/2026-07-04-phase-12c-maintainer-report.md (llama3.1:8b also failed the 50-word target) | documented |
| v10 | "it can't claim a pass it didn't earn" | run.py: summary passed = best_score >= threshold; final validators revert a synthesizer output that breaks the constraint; scripts/local_acceptance.sh guards the "silent pass" regression; release highlight "Safe failure on invalid output instead of silent pass" | TAKE: passed false; synthesizer output 193 words -> reverted to the best draft, 216 words (hard_fails synthesizer_constraint_violation 1); the loop 2 fixer claimed the limit was met at 360 words (research trial: synthesizer 144 words, reverted) |
| v11 | "every call ran locally, on a three-billion-parameter model" | config/models.yaml profile bootstrap (all seven roles llama3.2:3b; set as active_profile in the scratch clone, the README's documented switch); ollama base_url http://localhost:11434; take's metrics | TAKE and research trial: calls_by_model {"llama3.2:3b": 10}; ollama list: llama3.2:3b 2.0 GB |
| v11 | "with no API keys" | README "No API keys"; no key is read anywhere on the default path (cloud disabled) | true by default |
| v12 | "two hundred and twenty-seven tests" | `venv/bin/python -m pytest tests/ -q` on main @0f3f321: "227 passed in 9.33s"; same at v2.0.0 (227 passed); v2.0.0 release notes "227 passing tests"; ruff 0.6.9 "All checks passed!" | 227 passed (215 test functions, parametrized to 227; the career-hub's "215 tests" counts functions) |
| v12 | "the fifty-word bug included" | tests/test_pipeline_routing.py::test_pipeline_fails_when_supervisor_drops_original_word_limit (goal "Write a 50-word summary of why sleep matters.", a Supervisor that drops the limit, a 300-word draft, a passing Judge -> the pipeline must fail) | present, passes |
| v13 | "private multi-agent runs on your Mac" | app/streamlit_app.py hero subtitle: "Private multi-agent runs on your Mac." | verbatim |

## On screen

| Item | Source | Value |
|---|---|---|
| kicker "July 2026 · a test run of this project" | audit 6b, run id runs/20260704_171324/ | July 4, 2026 |
| "Ask for 50 words.", "about 450 words", "88/100 · Passed" | audit 6b | as above |
| brand line "Seven local agents · deterministic validators · no paid APIs" | docs/assets/brand/logo-sheet.png (the lockup's subtitle) | verbatim |
| "A model can't mark its own homework." | README | see v04 |
| address pill "localhost:8501" | README "Then open: http://localhost:8501"; record on port 8501 | only if the take is served on 8501 |
| segmented "fast · normal · deep", "25 words or fewer: fast" | orchestrator/router.py, config/models.yaml paths | FAST_PATH_WORD_THRESHOLD = 25 |
| "Refined goal: N words" | the take's 00_supervisor.json; router.py counts len(refined_goal.split()) | TAKE: "Summarize the importance of sleep in 50 words." = 8 words (<= 25 -> fast; pipeline.log path_selected fast) |
| judge row "'total_score': 84, 'pass': True" | the take (recorded UI, loop 1 judge row opened by the pointer) | TAKE: {'completeness': 22, 'accuracy': 20, 'clarity': 24, 'usefulness': 18}, 'total_score': 84, 'pass': True |
| "Current score 0/100" (Status tile) | the take (recorded UI) | TAKE: "0/100"; the Status tile reads "Belo..." (Streamlit truncates "Below threshold" at this column width, as in research at 1920 px): do not show "Below threshold" as if it were legible on screen |
| validator note "word count 216 is outside the 5-word tolerance for exact target 50" | the take's loop01_validators.json (capture/run/) | TAKE: 216 (builder draft 216 words) |
| "word count 360" | the take's loop02_validators.json | TAKE: 360 (loop 3: 401) |
| "meets the 50-word tolerance for exact target word count" (the model's own claim) | the take's loop 2 fixer row (recorded UI, opened by the pointer; capture/run/loop02_fixer.txt last sentence) | TAKE: "I also integrated the references into the text and ensured that the revised draft meets the 50-word tolerance for exact target word count." (that draft: 360 words). The judge did not repeat the claim in this take. The same row shows model-invented references above the claim: never push in on them |
| "Final score 0/100", "Result: Failed", "Loops 3", "Mode writing" | the take (recorded UI) and run_summary.json | TAKE: final_score 0, passed false, iterations_run 3, mode writing, path fast, stop_reason hard_fail: ['constraint_violation'] |
| caption "A high Judge score cannot rescue a draft that violates a checkable constraint" | app/streamlit_app.py (Validator failures) | verbatim, recorded |
| "word_limit · 3" | the take's metrics.validator_failures (dashboard table: rule word_limit, times failed 3) | TAKE {"word_limit": 3} |
| metrics table (role, model llama3.2:3b, calls, elapsed_ms), "Total runtime: N s" | the take (recorded UI) and run_summary.json metrics | TAKE "Total runtime: 646.2s"; supervisor 1 call 45,678 ms; builder 1 / 64,488; judge 3 / 118,520; critic 2 / 165,776; fixer 2 / 204,757; synthesizer 1 / 46,835; calls_by_model llama3.2:3b 10; retries 0, fallbacks 0, timeout events 0 (the machine was shared with five other renders, load average 300-440: the times say nothing about the model's normal speed) |
| speed chips ("22× speed", "114× speed") | assets/edit.json shots[].speed: factor = real seconds of model work / film seconds (capture/conform.py) | TAKE: s3-s4 22.95-30.42 at 21.7-21.8x (129.1 s real) -> "22× speed"; s5 38.82-40.73 at 114.4x (214.5 s real) -> "114× speed"; typing, clicks and scrolls play at 1x |
| "227", "tests passed", "pytest · main @0f3f321" | pytest run above | 227 |
| "test_pipeline_fails_when_supervisor_drops_original_word_limit" | tests/test_pipeline_routing.py line 227 | verbatim |
| URL "github.com/andyyaro/local-ai-orchestrator" | gh api repos/andyyaro/local-ai-orchestrator (public, created 2026-07-03) | live |
| logo, dial mark, wordmark | docs/assets/brand (copied to assets/brand/) | Familjen Grotesk Bold wordmark (outlined); #1E2A1A, #C5D86D, #F1EEDC |

## Background facts (not planned on screen; checked)

- Solo project, Jul 3 to 5, 2026 (career-hub projects/local-ai-orchestrator.md). 170 commits on main today (GitHub
  API, last page of per_page=1); the career-hub's 169 predates the Nov 1 logo commit.
- About 10,700 lines of Python in the repo (`wc -l` over *.py: 10,742); career-hub says ~11,000.
- v2.0.0 highlights: routing, validators, resilience, metrics, memory discipline, cloud fallback scaffolding (off),
  retrieval and research scaffolding, a coding-agent subsystem, an eval suite, split release gates.
- Coding mode runs generated Python and pytest in a sandbox; broken code is a hard fail (orchestrator/code_runner.py,
  run.py _apply_code_verification_to_verdict). Not in the film's run (the goal is writing mode).

## Not claimed, on purpose

- "Open source" / "MIT": the README says MIT and the brand sheet says "Open source", but the repo has no LICENSE file
  (GitHub reports license null). The film makes no licence claim.
- "No internet": true by default in config (research.internet_enabled false) but not tested offline here; the film
  says "no API keys" and "no paid API calls" instead.
- No users, downloads, stars (1), benchmarks or speed claims. The model's own text in the run (it invents statistics,
  e.g. "a 2015 meta-analysis") is never presented as fact.

## Found in research (worth telling Andy)

- With the pinned Streamlit 1.58.0 the dashboard's sidebar cannot be opened: the app's CSS hides
  [data-testid="stToolbar"], which now contains the expand-sidebar button. Path, loops, threshold and model overrides
  are unreachable from the UI.
- The app's CSS asks for Inter, but its selector `[class*="css"]` no longer matches Streamlit 1.58's class names, so
  the page renders in Source Sans; the Run pipeline label renders dark on the dark-green button.
- Under heavy machine load (load average 95), llama3.2:3b hit the 120 s "small" timeout and the run stopped with
  "Pipeline error: builder: 'llama3.2:3b' timed out and no distinct fallback model is configured" (the bootstrap
  profile's fallback is the same model).

## The film's take (capture stage, 2026-11-01)

Recorded by capture/takes.py in the real dashboard (Streamlit 1.58.0, the scratch clone at main @0f3f321, bootstrap profile,
http://localhost:8501, 1280 x 720 at 2x), run ui_20261101_230242, started 23:02:42, typed goal "Write a 50-word summary of why
sleep matters." Its own files are copied to capture/run/ (run_summary.json, loopNN_validators.json, loopNN_judge.json, the
drafts, and dashboard-text.txt, the page's text without the "Run saved to:" line). Every on-screen number above marked TAKE is
from these files or the recorded frames.

| Step | Value (take) |
|---|---|
| supervisor | refined goal "Summarize the importance of sleep in 50 words." (8 words), mode writing -> path fast |
| builder | 216 words |
| loop 1 judge (UI row, before the validator) | 22 + 20 + 24 + 18, 'total_score': 84, 'pass': True |
| loop 1 validator | "word count 216 is outside the 5-word tolerance for exact target 50" -> score 0, Current score 0/100 |
| loop 2 critic, fixer | the fixer's draft 360 words; its last sentence claims it "meets the 50-word tolerance for exact target word count" |
| loop 2 validator | "word count 360 is outside the 5-word tolerance for exact target 50" (judge file: 22 + 20 + 23 + 19, forced 0) |
| loop 3 | draft 401 words, forced 0 (judge 24 + 20 + 22 + 20) |
| synthesizer | 193 words, breaks the constraint -> reverted to the best draft (216 words); hard_fails synthesizer_constraint_violation 1 |
| Run summary | Final score 0/100, Result Failed, Loops 3, Mode writing; scores [0, 0, 0]; stop reason hard_fail: ['constraint_violation'] |
| metrics | 10 calls, all llama3.2:3b; total 646.2 s (shared, overloaded machine) |

The narration v05-v11 matches this take as voiced (fast path, a judge pass then a forced zero, the critic and fixer try again,
three loops still too long, Failed, every call on llama3.2:3b): no re-voicing, Variant B not used.
