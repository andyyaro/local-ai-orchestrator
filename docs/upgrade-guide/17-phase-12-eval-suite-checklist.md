# 17 — Phase 12: Final Eval Suite and Release Checklist

## Goal

Prove the upgraded system actually works — end to end, on real models where
it matters — before merging any phase branch into `main` or requesting a
release, using one eval suite that exercises every phase built so far and
one final checklist you run every single time.

## Why it matters

Every phase from 0 through 11 has its own local test suite
(`tests/test_validators.py`, `tests/test_router.py`, and so on), and those
all run against mocked adapters in CI (Phase 1). That's necessary but not
sufficient — it proves the code is internally consistent, not that the
*system* behaves correctly on a real goal with a real model. This phase adds
the missing layer: a small set of realistic end-to-end scenarios, each one
tied directly to a specific problem this guide set out to fix, plus a
literal checklist you run before any merge or release so "did I check
everything" stops being a memory exercise.

This suite is explicitly a **human-run acceptance step**, not a CI job — it
belongs in a new top-level `eval/` folder, separate from `tests/`, because
several of its scenarios need a real Ollama model and are too slow and too
hardware-dependent to run automatically on every push. Track A (CI) checks
code correctness on every push; this eval suite checks *system* correctness
before you personally decide to merge or release, matching the three-track
model from `00-overview.md`.

## Files likely touched

```text
eval/                     (new top-level folder)
eval/scenarios.py         (new — one function per eval task)
eval/run_eval_suite.py    (new — runner that executes available scenarios and reports pass/fail/skipped)
```

Files to inspect first (read-only) — this phase touches almost everything
built in Phases 2–11, so re-familiarize yourself with whichever of these
actually exist in your repo at this point:

```text
orchestrator/validators.py
agents/judge.py
orchestrator/code_runner.py
orchestrator/resilience.py
orchestrator/cloud_policy.py
orchestrator/cost_tracker.py
orchestrator/privacy_guard.py
memory/retriever.py
research/citation_verifier.py
app/streamlit_app.py
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-12-eval-suite
```

2. Create `eval/scenarios.py` with one function per eval task. Each function
   should return a simple `EvalResult` (status: `"pass"`, `"fail"`, or
   `"skipped"`, plus a message) and must **skip gracefully, not fail**, if
   the phase it depends on hasn't been implemented yet in your repo — check
   this guide's earlier phase files match reality with a plain `try:`
   `import` at the top of each scenario function rather than assuming every
   phase exists.

   - `eval_exact_word_limit()` — runs the real pipeline (small model) with a
     goal like "Write a summary of the water cycle in exactly 120 words,"
     and asserts the final output is within Phase 2's validator tolerance.
     This is the direct regression test for the bug that started this
     entire guide — treat any failure here as the highest-priority thing to
     fix before anything else in this checklist.
   - `eval_json_only_judge()` — calls the real Judge agent (not mocked) on a
     sample draft and asserts the response parses as valid JSON matching
     the schema in `prompts/judge.txt`, catching real-world prompt drift
     that a mocked unit test can't.
   - `eval_simple_coding_task()` — runs a coding-mode goal end to end and
     asserts `code_verification` succeeded and pytest passed inside the
     pipeline's own verification step.
   - `eval_timeout_fallback()` — (Phase 4) deliberately points a role at an
     unreasonably short timeout or a model likely to be slow, and asserts
     the run completes via fallback rather than crashing, and that
     `run_summary.json`'s metrics show a recorded fallback event.
   - `eval_local_only_no_cloud()` — (Phase 7) runs a normal goal with the
     shipped default config (`cloud.enabled: false`) and asserts zero new
     rows were added to the `cloud_calls` table for that run.
   - `eval_cloud_mock_fallback()` — (Phase 7) using `MockCloudAdapter` only,
     simulates an approved escalation and asserts exactly one `cloud_calls`
     row was recorded with a plausible cost — never a real network call.
   - `eval_privacy_redteam()` — (Phase 7) constructs a payload containing an
     obviously fake secret pattern and asserts `privacy_guard.guard_payload`
     raises before anything would be sent.
   - `eval_cost_budget_block()` — (Phase 7) seeds the `cloud_calls` table
     with spend already at the configured daily budget and asserts the next
     call is blocked before human approval is even requested.
   - `eval_retrieval()` — (Phase 9) indexes a known run, then asserts
     `retrieve_context()` for a related goal returns content referencing
     it, and never returns more than the configured `top_k` chunks.
   - `eval_citation_verification()` — (Phase 10) constructs a report
     containing one fabricated citation and asserts
     `reject_unverified_citations` flags exactly that claim and no other.
   - `eval_streamlit_smoke()` — runs `python -c "import app.streamlit_app"`
     as a subprocess and asserts it exits cleanly.

3. Create `eval/run_eval_suite.py` — a small CLI script that imports and
   runs every scenario from `eval/scenarios.py`, prints a clear pass/fail/
   skipped table, and exits non-zero if anything genuinely failed (skipped
   scenarios for not-yet-implemented phases do not count as failures).

```bash
python eval/run_eval_suite.py
```

4. Run this suite before merging **any** phase branch from Phase 2 onward,
   not just at the very end of all 12 phases — it's written to skip
   gracefully specifically so it stays useful throughout, not only as a
   final gate.

## The final release checklist

Run this literal checklist before merging any phase branch into `main`, and
again before requesting an actual GitHub release. Copy it into your PR
description if that helps you track it.

```text
[ ] git status --short          -> clean, or only the intended files changed
[ ] ruff check .                -> passes
[ ] pytest tests/ -v            -> all pass
[ ] python eval/run_eval_suite.py -> no genuine failures (skips are fine)
[ ] bash scripts/local_acceptance.sh -> passes, if Phase 6 has landed
[ ] streamlit run app/streamlit_app.py -> manually confirmed working
[ ] No accidental cloud calls -- confirm cloud_calls table row count
    didn't change during a cloud.enabled: false run
[ ] No secrets in logs -- grep logs/pipeline.log and any eval output
    for API-key-shaped strings before sharing or committing anything
[ ] No generated junk committed -- git status --short shows nothing under
    runs/, logs/, .venv/, or __pycache__/
[ ] No git tag was created
[ ] No GitHub release was created unless explicitly requested
```

A concrete command for the secrets-in-logs check:

```bash
grep -Ei "sk-[a-z0-9]{10,}|api[_-]?key|bearer [a-z0-9]" logs/pipeline.log
```

Expected result: no matches. If it finds something, treat it as a real
incident — figure out which phase's code path logged it, fix that code path
so the value is never printed or written to the log file, and do not commit
or share the log until you've confirmed the fix.

## Tests to add

`eval/` scenarios are themselves the "tests to add" for this phase — there
is no separate `tests/test_eval_suite.py`, since these scenarios
intentionally call real models and real (mocked, where noted) external
boundaries, which doesn't belong in the CI-run `tests/` directory. If you
want a CI-safe check that the eval suite itself is at least importable and
doesn't crash on missing phases, add a minimal smoke test:

```python
# tests/test_eval_suite_importable.py
def test_eval_suite_imports():
    import eval.scenarios  # noqa: F401
```

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
git status --short
ruff check .
pytest tests/ -v
python eval/run_eval_suite.py
```

## Expected output

- The full `tests/` suite passes.
- `eval/run_eval_suite.py` prints a clear per-scenario pass/fail/skipped
  table, with zero genuine failures (skips for not-yet-built phases are
  expected and fine).
- The final release checklist above is fully checkable with no surprises.

## If it fails

- `eval_exact_word_limit` fails: this is the original bug — stop everything
  else and fix Phase 2's validator wiring before proceeding with any other
  checklist item.
- A scenario for a phase you know you've implemented reports `"skipped"`
  instead of running: check the scenario's `try:`/`import` — a typo in an
  import path will silently skip a real check, which defeats the purpose;
  treat an unexpectedly-skipped scenario for a phase you believe is done as
  its own bug to investigate.
- The secrets-in-logs grep finds something: do not just delete the log line
  — trace which module wrote it and fix the underlying logging call so the
  secret is never captured in the first place (mirroring Phase 7's privacy
  guard discipline — fail closed, fix root cause, don't just hide the
  symptom).

## Rollback plan

This phase only adds an evaluation script and a checklist — it makes no
changes to pipeline behavior, so there is effectively nothing to "roll
back" in the sense of undoing a behavioral regression. If you want to
remove the `eval/` folder entirely:

```bash
git rm -r eval/
git commit -m "chore: remove eval suite"
```

## Commit suggestion

```text
test: add end-to-end eval suite and final release checklist
```

## Done when

```text
The branch is ready for human review: the eval suite runs cleanly (genuine
failures at zero, skips only for phases not yet built), the final release
checklist is fully satisfied, and you have personally read the diff, not
just trusted a green check.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 12: the final eval suite.

Before editing, run:
git status --short
git branch --show-current

Then inspect whichever of these files actually exist in this repo (some may
not, if earlier phases haven't landed yet -- report which are missing
rather than assuming):
- orchestrator/validators.py
- agents/judge.py
- orchestrator/code_runner.py
- orchestrator/resilience.py
- orchestrator/cloud_policy.py
- orchestrator/cost_tracker.py
- orchestrator/privacy_guard.py
- memory/retriever.py
- research/citation_verifier.py
- app/streamlit_app.py

Implement the following:
1. Create eval/scenarios.py with one function per eval task: exact word
   limit, JSON-only Judge, simple coding task, timeout fallback, local-only
   no-cloud, cloud mock fallback, privacy red-team, cost-budget block,
   retrieval, citation verification, and a Streamlit import smoke test.
   Each function must gracefully report "skipped" (not "failed") if the
   phase it depends on doesn't exist in this repo yet -- use a try/import
   pattern, and report exactly which import failed if you skip one.
2. Create eval/run_eval_suite.py: a CLI script importing and running every
   scenario, printing a clear pass/fail/skipped table, and exiting non-zero
   only on a genuine failure (never on a skip).
3. Add a minimal tests/test_eval_suite_importable.py that just imports
   eval.scenarios, so CI can at least catch an import-breaking typo.

Do not modify any file outside this scope.
Do not enable cloud calls or change the active provider -- any cloud-related
scenario must use MockCloudAdapter only.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/ -v
- python eval/run_eval_suite.py
- git status --short

Stop after reporting:
1. Files changed
2. Which phases were found present vs. missing in this repo (and therefore
   which eval scenarios ran vs. skipped)
3. The eval suite's pass/fail/skipped results
4. Any remaining risks or TODOs
5. A suggested commit message
```
