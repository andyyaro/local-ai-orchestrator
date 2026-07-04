# 13 — Phase 8: Streamlit Updates

## Goal

Expose the new controls and information from Phases 2–7 (selected path,
validator failures, metrics summary, cloud status/approval/cost) in the
Streamlit dashboard, without making the UI flashy or cluttered.

## Why it matters — an important finding this phase must address first

Direct inspection of `app/streamlit_app.py` found something the earlier
phases did not account for: **the Streamlit app does not call `run.py`'s
`run_pipeline()` at all.** It has its own separate, independent
implementation — `run_pipeline_thread()` (starting around line 183) — which
imports the agent classes directly (`SupervisorAgent`, `PlannerAgent`, and so
on) and reimplements the loop, including its own copies of
`apply_code_verification_to_verdict()` and `should_break_on_hard_fail()`
(around lines 130–168) that duplicate logic already in `run.py`.

This means the project has **three** parallel pipeline implementations, not
two: `run.py`, `orchestrator/graph.py` (LangGraph), and now confirmed,
`app/streamlit_app.py`'s own `run_pipeline_thread()`. Every phase from 2
through 7 (validators, routing, resilience, metrics, cloud fallback) was
wired into `run.py` and, where noted, `orchestrator/graph.py` — but **none of
that logic exists in the Streamlit app's thread today**, and it will not
appear there automatically.

This matters because "expose new controls in Streamlit" is not just a
display task — the underlying data (selected path, validator results,
metrics, cloud approval state) does not currently flow through the
Streamlit app's pipeline at all. Before adding UI elements, you have to
decide how that data gets there. Two options, and the tradeoff to make
explicitly rather than by default:

**Option A — Refactor `app/streamlit_app.py` to call `run.py`'s
`run_pipeline()` directly** (adapting it to emit progress events to the
Streamlit event queue instead of `print()`-ing to a terminal), deleting the
duplicated `apply_code_verification_to_verdict()` /
`should_break_on_hard_fail()` copies. This is more work up front, but it
means every future phase only needs to be wired into `run.py` once, and the
Streamlit app never drifts out of sync again. **This is the recommended
option** — three copies of the same pipeline logic is exactly the kind of
complexity the project should not be carrying, and it is what caused this
gap to go unnoticed until now.

**Option B — Manually re-port each phase's logic into
`run_pipeline_thread()`** a third time, matching what `run.py` already does.
This is faster in the short term but guarantees the same problem recurs at
the next phase — do not choose this option unless you have a specific,
stated reason `run.py` cannot be safely called from a background thread in
this app.

This guide recommends Option A. If you choose Option B instead, do so
explicitly and note it as a deliberate, scoped tradeoff — not a default.

## Files likely touched

```text
app/streamlit_app.py   (refactored to call run.py's run_pipeline(), or updated in place per Option B)
```

Files to inspect first (read-only):

```text
app/streamlit_app.py
run.py
orchestrator/router.py
orchestrator/validators.py
orchestrator/resilience.py
orchestrator/metrics.py
orchestrator/cloud_policy.py
orchestrator/cost_tracker.py
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-8-streamlit-updates
```

2. Decide and record which option (A or B) you're taking, per the section
   above, before writing any UI code.

3. If Option A: refactor `run.py`'s `run_pipeline()` so its progress
   reporting is pluggable — for example, accept an optional `on_step`
   callback parameter that both the terminal (`print`-based) and Streamlit
   (`event_queue`-based) callers can pass in, rather than `run_pipeline()`
   calling `print()` directly. Then have `app/streamlit_app.py` import and
   call `run_pipeline()` from a background thread, passing a callback that
   posts to `event_queue` (reusing the existing `emit_step()` helper's
   shape). Delete `run_pipeline_thread()`'s duplicated
   `apply_code_verification_to_verdict()` and `should_break_on_hard_fail()`
   — they should no longer exist once the app calls the real
   `run_pipeline()`.

4. Add UI elements, without over-designing:

   - **Selected path** (Phase 3): a small status pill or caption near the
     existing `render_status_pill("Local only", "green")` call (sidebar,
     around line 797) showing `"fast"` / `"normal"` / `"deep"` once a run
     completes, read from `summary["path"]`.
   - **Validator failures** (Phase 2): if `run_summary.json`'s
     `validator_failures` (via Phase 5's metrics) is non-empty, show it
     plainly in the run results area — the specific rule that failed and
     its detail message, not just a generic "failed" indicator.
   - **Metrics summary** (Phase 5): a compact table or small set of
     captions showing total runtime, per-agent time breakdown, and
     `calls_by_model` — this is the view that lets you visually confirm
     Phase 6 actually reduced distinct large-model usage in one run. Do not
     build a full charting dashboard here; a plain `st.dataframe` or a
     handful of `st.metric()` calls is enough.
   - **Cloud disabled/enabled status** (Phase 7): replace the hardcoded
     `render_status_pill("Local only", "green")` with one that actually
     reads `cloud_policy.is_cloud_enabled()` — it must not keep claiming
     "Local only" once cloud fallback has been enabled in config, since a
     hardcoded status pill that doesn't reflect real config is worse than
     no pill at all.
   - **Cloud cost preview and approval panel** (Phase 7): if cloud fallback
     is enabled and a role's step is about to be escalated, show the exact
     payload preview and estimated cost `orchestrator/cloud_policy.py`
     already builds, with an explicit approve/deny button — this is the
     same human-gate from Phase 7, just rendered in the UI instead of a
     terminal `y`/`n` prompt. Do not add a "remember my choice" or
     "always approve" toggle — every cloud call gets its own explicit
     approval, by design.
   - **Fallback events** (Phase 4): if a run recorded a model fallback
     (Phase 5's `fallbacks` count), surface it plainly — for example
     "Judge fell back from qwen2.5:14b to llama3.2:3b after a timeout" —
     so a degraded-quality run is visible, not silent.

5. Keep the existing model-override dropdowns (sidebar, around lines
   762–795) but confirm their hardcoded option lists (`"qwen2.5:14b"`,
   `"qwen2.5-coder:14b"`, `"phi4:14b"`, `"gemma3:12b"`, and so on) still
   match whatever Phase 6 actually settled on for the `serious`/`coding`
   profiles — if Phase 6 changed which models are used for which roles,
   these dropdowns need to match, or they'll offer choices that don't
   correspond to what the profiles actually do anymore.

## Tests to add

Streamlit UI code is not unit-tested the way pipeline logic is (there is no
existing precedent for it in `tests/`, and adding browser-based UI tests is
out of scope for this phase). Instead:

- If Option A was taken, `run.py`'s existing tests (and any new tests added
  for the `on_step` callback parameter) confirm `run_pipeline()` still works
  correctly when called with a callback, not just when run standalone from
  `main()`.
- Add a plain import/smoke test if one doesn't already exist:
  `python -c "import app.streamlit_app"` succeeds with no import errors
  (this may already be covered by Phase 1's CI workflow).

## Commands to run

```bash
ruff check .
pytest tests/ -v
python -c "import app.streamlit_app"
streamlit run app/streamlit_app.py
```

## Expected output

- `ruff check .` and `pytest tests/ -v` pass.
- The Streamlit import smoke test passes.
- Launching the dashboard manually and running a real small-model goal
  shows the new path/validator/metrics/cloud-status elements without the
  page becoming visually cluttered — if you can't describe what happened in
  a run by glancing at the results area for a few seconds, it's too busy.

## If it fails

- After refactoring to call `run.py`'s `run_pipeline()`, the Streamlit
  thread hangs or the UI doesn't update: check that the `on_step` callback
  is actually thread-safe with Streamlit's `event_queue` pattern — the
  existing `emit_step()` helper already handles this correctly for the old
  inline implementation, so reuse its exact queue-posting mechanism rather
  than inventing a new one.
- The cloud approval panel doesn't appear even with `cloud.enabled: true`:
  confirm `--allow-cloud`'s CLI-flag gate from Phase 7 has a UI equivalent
  (a checkbox or toggle) — a UI run has no command line, so Phase 7's
  CLI-flag condition needs a corresponding UI control, not silent bypassing.
- The model-override dropdowns list models that Phase 6 no longer uses in
  any profile: update the dropdown option lists to match Phase 6's actual
  profile contents, or remove models that no longer appear anywhere in
  `config/models.yaml`.

## Rollback plan

If Option A's refactor introduces a regression in the Streamlit app that's
hard to pin down quickly, revert just this phase and keep the triplicated
implementation temporarily rather than shipping a half-refactored app:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-8-streamlit-updates
```

## Commit suggestion

```text
refactor: unify Streamlit app on run.py's pipeline and surface path/validator/metrics/cloud status
```

## Done when

```text
The Streamlit UI shows what the orchestrator did without becoming visually
messy: selected path, validator failures, a compact metrics summary, real
(non-hardcoded) cloud status, cloud cost/approval when applicable, and
fallback events — and, if Option A was taken, app/streamlit_app.py no longer
contains a duplicated copy of pipeline logic that exists in run.py.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 8: Streamlit updates.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- app/streamlit_app.py
- run.py
- orchestrator/router.py
- orchestrator/validators.py
- orchestrator/resilience.py
- orchestrator/metrics.py
- orchestrator/cloud_policy.py
- orchestrator/cost_tracker.py

First, report back: app/streamlit_app.py's run_pipeline_thread() (around
line 183) independently reimplements the pipeline rather than calling
run.py's run_pipeline(), including duplicated copies of
apply_code_verification_to_verdict() and should_break_on_hard_fail() (around
lines 130-168). Confirm this is still the case, then propose whether to
refactor run_pipeline() to accept a pluggable on_step callback so
app/streamlit_app.py can call it directly (recommended), or to manually
port each phase's logic into run_pipeline_thread() a third time. Wait for
approval on which approach before making changes.

Once approach is confirmed, implement it, then add UI elements: selected
path (Phase 3) near the existing status pill, validator failures (Phase 2)
in the run results area, a compact metrics summary (Phase 5, not a full
charting dashboard), a cloud status indicator that reads
cloud_policy.is_cloud_enabled() instead of the current hardcoded "Local
only" pill, a cloud cost/approval panel if cloud fallback is enabled
(Phase 7 - no "always approve" shortcut), and fallback events (Phase 4) if
any occurred. Also verify the model-override dropdown option lists still
match Phase 6's actual profile contents.

Do not modify any file outside app/streamlit_app.py (and run.py only if the
callback refactor requires it, and only in a minimal, scoped way).
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/ -v
- python -c "import app.streamlit_app"
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Which option (A or B) was taken for the pipeline-duplication finding, and why
4. Any remaining risks or TODOs
5. A suggested commit message
```
