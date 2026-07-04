# Phase 12 Maintainer Report — Final Eval Suite and Release Checklist

## Goal

Prove the upgraded system actually works — end to end, on real models
where it matters — before merging any phase branch or requesting a
release, using one eval suite that exercises every phase built so far
and one final checklist run every time.

## What was built

1. **`eval/scenarios.py`** — 11 scenario functions, each returning a
   plain `EvalResult(name, status, message)` with `status` in
   `{"pass", "fail", "skipped"}`. Every function wraps its phase-specific
   imports in `try:`/`except ImportError` and reports `"skipped"` (never
   `"fail"`) if that phase isn't present — and, where relevant, if a real
   external dependency the scenario needs (a pulled embedding model) is
   genuinely unavailable, since this project never downloads anything
   automatically, including from an eval scenario.
2. **`eval/run_eval_suite.py`** — CLI runner: imports and executes every
   scenario in `eval.scenarios.ALL_SCENARIOS`, prints a live per-scenario
   result plus a summary table, and exits non-zero only if something
   genuinely failed (a skip never counts as a failure). Includes a
   `sys.path` fix so it works both as `python eval/run_eval_suite.py`
   (the guide's documented invocation) and `python -m eval.run_eval_suite`.
3. **`tests/test_eval_suite_importable.py`** (CI-safe) — confirms
   `eval.scenarios` imports cleanly and `ALL_SCENARIOS` is a non-empty
   list of callables, so a typo in an import path is caught automatically
   on every push, without needing a real model in CI.

## Scenario design notes worth recording

- **Scenarios that touch `cloud_calls` purely for synthetic testing**
  (`eval_cloud_mock_fallback`, `eval_cost_budget_block`) redirect
  `orchestrator.database.DB_PATH` to a throwaway temp file for the
  duration of the check, restoring the original path in a `finally`
  block. This keeps the check exercising real database code (not mocks)
  while never polluting the user's real `runs/history.db` with synthetic
  cost/budget data.
- **`eval_local_only_no_cloud`** intentionally uses the real database (no
  redirect) — it needs a genuine pipeline run to prove no cloud call
  happened, and a legitimate small-goal run entering real run history is
  the same kind of side effect `scripts/local_acceptance.sh` already
  produces every time a human runs it manually.
- **`eval_retrieval`** calls the real `embed()` → real Ollama
  `/api/embeddings` endpoint via `memory.indexer.index_run()`. Since
  `nomic-embed-text` is not pulled in this environment (confirmed via
  `ollama list` in Phase 9), this correctly and gracefully reports
  `"skipped"` with the exact `ollama pull nomic-embed-text` command,
  rather than failing or silently pulling the model.
- **`eval_timeout_fallback`** forces a real, fast, deterministic timeout:
  the resilience config's "medium" timeout class is monkeypatched down to
  1 second (guaranteed too short for any real generation) while the
  fallback model's "small" timeout class is left at a generous 60
  seconds — so the primary model call reliably times out in ~1 second,
  triggering a genuine fallback, without an artificial sleep or a
  multi-minute wait.

## A real design flaw caught and fixed during the first eval run

The first full run of `eval_exact_word_limit` reported `FAIL`, but
inspecting *why* revealed the scenario's own assertion was wrong, not the
pipeline: the run had correctly detected the constraint violation
(`stop_reason: hard_fail: ['constraint_violation']`, `passed: False`) —
exactly Phase 2/6b/6c's safety net working as designed on a real model
call that didn't land within tolerance. The scenario's original logic
conflated "the raw output doesn't satisfy the word count" with "the
original silent-pass bug," when the actual regression signature is
`passed: True` **despite** violating the constraint — that never
happened. Fixed the scenario to check for that specific signature
instead, and verified the fix against both:
- the real observed case (a correctly-refused violation) — now reports
  `pass`, confirmed via a scripted replay of the exact real
  `summary`/`final_output` the first run produced (no need to re-run the
  ~18-minute real pipeline call a third time just to re-verify logic);
- a constructed true-regression case (`passed: True` with a
  still-violating draft) — confirmed this **still correctly fails**.

A second full eval suite run with the fix in place completed with
`eval_exact_word_limit: PASS` in 282.8 seconds.

## A genuine, reproducible finding: `eval_simple_coding_task`

`eval_simple_coding_task` failed in **all three runs** (the original full
run, an isolated retry, and the final full re-run) with the same root
cause: the Supervisor classified the goal *"Write a Python function
called double(n) that returns n multiplied by 2. Include a pytest test
asserting double(5) == 10."* as `mode: "general"`, not `mode: "coding"`,
using `llama3.1:8b` (the `serious` profile's default supervisor model).
Inspected the raw `00_supervisor.json` output directly to confirm this —
it is a real, consistent model/prompt behavior, not a fluke or a bug in
the eval scenario itself (the goal text is about as unambiguously a
coding task as a goal can be phrased, and `prompts/supervisor.txt`
already lists "coding: writing new Python code, functions, scripts, or
programs" as a mode option).

**This was not fixed in this phase.** Phase 12's explicit scope is
adding the eval suite itself, not modifying `prompts/supervisor.txt` or
any other pipeline file — and this is precisely the kind of "real-world
prompt drift a mocked unit test can't catch" the guide describes
`eval_json_only_judge` as existing to surface. Recorded here as a
genuine, actionable finding for a future, explicitly-scoped fix (e.g.
strengthening the coding-mode classification examples in
`prompts/supervisor.txt`, or trying a different supervisor-role model),
not silently engineered around by rewording the eval's goal until it
happened to pass.

## Final eval suite result

```
  Scenario                                      Status       Time
  --------------------------------------------- -------- --------
  eval_exact_word_limit                         PASS      282.8s
  eval_json_only_judge                          PASS       98.6s
  eval_simple_coding_task                       FAIL      291.7s
  eval_timeout_fallback                         PASS        5.9s
  eval_local_only_no_cloud                      PASS       97.6s
  eval_cloud_mock_fallback                      PASS        0.0s
  eval_privacy_redteam                          PASS        0.0s
  eval_cost_budget_block                        PASS        0.0s
  eval_retrieval                                SKIPPED     0.0s
  eval_citation_verification                    PASS        0.0s
  eval_streamlit_smoke                          PASS        1.4s

  9 passed, 1 failed, 1 skipped (out of 11 scenarios)
```

`run_eval_suite.py` exited non-zero (1) due to the one genuine failure
above (`eval_simple_coding_task`) — the checklist item "no genuine
failures (skips are fine)" is **not** fully satisfied as of this phase,
and that's reported honestly rather than hidden.

## Tests run

```
ruff check .                              → All checks passed!
pytest tests/test_eval_suite_importable.py → 2 passed (import + ALL_SCENARIOS shape)
pytest tests/ -v                          → 203 passed
python eval/run_eval_suite.py             → 9 passed, 1 failed, 1 skipped (see above)
```

## Final release checklist (run for this phase)

```
[x] git status --short          -> only eval/ and tests/test_eval_suite_importable.py (intended)
[x] ruff check .                -> passes
[x] pytest tests/ -v            -> all 203 pass
[~] python eval/run_eval_suite.py -> 9 passed, 1 failed (eval_simple_coding_task,
    a genuine finding, not an eval bug), 1 skipped (embedding model not pulled)
[ ] bash scripts/local_acceptance.sh -> not re-run in this phase (already verified
    in Phase 6b/6c; no pipeline behavior changed in Phase 12)
[ ] streamlit run app/streamlit_app.py -> not live-launched (sandboxed session,
    no outbound network/port access -- same limitation noted in Phase 8)
[x] No accidental cloud calls -- eval_local_only_no_cloud confirmed
    cloud_calls row count unchanged (0) across the run
[x] No secrets in logs -- grepped logs/pipeline.log (4134 lines) for
    sk-[a-z0-9]{10,}|api[_-]?key|bearer [a-z0-9]: zero matches
[x] No generated junk committed -- git status --short shows nothing
    under runs/, logs/, .venv/, or __pycache__/
[x] No git tag was created
[x] No GitHub release was created
```

## Files changed

- `eval/__init__.py` (new)
- `eval/scenarios.py` (new)
- `eval/run_eval_suite.py` (new)
- `tests/test_eval_suite_importable.py` (new)
- `docs/audits/2026-07-04-phase-12-maintainer-report.md` (new)

## Remaining risks / TODOs

- **`eval_simple_coding_task` fails against the current `serious` profile
  and `prompts/supervisor.txt`** — a real, reproducible finding (see
  above), not yet fixed. This is the one concrete, actionable item a
  human should look at before treating the eval suite as fully green.
- `eval_retrieval` will keep reporting `"skipped"` until
  `nomic-embed-text` is pulled locally (`ollama pull nomic-embed-text`) —
  expected and by design, not a bug.
- The eval suite's real-model scenarios are meaningfully slower than
  their first-run numbers might suggest across different environments —
  `eval_exact_word_limit` alone took anywhere from 283s to 1099s across
  three runs in this session, purely from real model variance (retry
  attempts inside the repair loop, JSON-parse retries in the Judge,
  etc.). Budget real wall-clock time (potentially 10-20+ minutes for the
  full suite) when running this before a merge.
- `scripts/local_acceptance.sh` and a live `streamlit run` launch were not
  re-verified in this specific phase, since Phase 12 makes no pipeline
  behavior changes — both were already verified in their respective
  phases (6b/6c and 8).

## Commit

```
test: add end-to-end eval suite and final release checklist
```
