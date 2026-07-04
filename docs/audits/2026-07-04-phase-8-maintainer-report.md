# Phase 8 Maintainer Report — Streamlit Updates

## Goal

Expose the new controls and information from Phases 2–7 (selected path,
validator failures, metrics summary, cloud status/approval/cost) in the
Streamlit dashboard, without making the UI flashy or cluttered.

## The pipeline-duplication finding — confirmed

Direct inspection confirmed the guide's finding: `app/streamlit_app.py`'s
`run_pipeline_thread()` (previously ~290 lines, starting around line 183)
independently reimplemented the entire pipeline — importing agent classes
directly and maintaining its own copies of
`apply_code_verification_to_verdict()` and `should_break_on_hard_fail()` —
rather than calling `run.py`'s `run_pipeline()`. This meant Phases 2
(validators), 3 (routing), 4 (resilience retry/fallback), 5 (metrics), 6
(memory discipline), and 7 (cloud gating) were all wired into `run.py` but
**none of that logic existed in the Streamlit app's thread**.

## Decision: Option A (recommended by the guide)

Took **Option A**: refactored `run.py`'s `run_pipeline()` to accept a
pluggable `on_step` callback, and rewrote `app/streamlit_app.py`'s
`run_pipeline_thread()` to call the real `run_pipeline()` directly from
its background thread, deleting the duplicated
`apply_code_verification_to_verdict()` and `should_break_on_hard_fail()`
copies entirely (along with `collect_iterations()`, `role_model()`,
`emit_step()`, `save()`, and `score_bar()` — all now either redundant or
replaced). This was chosen over Option B (re-porting each phase's logic a
third time) because the guide correctly identifies that as guaranteeing
the same drift recurs at the next phase — the whole reason this gap
existed for six phases without anyone noticing.

## What changed

### `run.py` (minimal, scoped to the callback)

- `_log_agent_call()` gained an optional `on_step=None` parameter: emits
  `{"type": "step", "agent": ..., "status": "running"}` before the call
  and `{"type": "step", "agent": ..., "status": "done"/"error", ...}`
  after — the exact same event shape the old Streamlit implementation's
  `emit_step()` already used, so the UI's rendering code for these events
  needed no changes.
- `_run_critic_fixer_judge_iteration()` and `run_pipeline()` both thread
  `on_step` through to every agent call and loop boundary (`loop_start`/
  `loop_result` events at each iteration, including the Phase 6c fast-path
  repair loop).
- `run_pipeline()` gained the `on_step` parameter with a docstring
  explaining its purpose. When `on_step` is `None` (the terminal `main()`
  path, unchanged), behavior is byte-for-byte identical to before this
  phase — confirmed by the full existing test suite passing unmodified.

### `app/streamlit_app.py` (the bulk of the change: 535 lines removed, ~120 added net)

- `run_pipeline_thread()` is now an ~25-line wrapper: calls `run.py`'s
  `run_pipeline()` with `on_step=lambda event: event_queue.put(event)`,
  then posts a `"final"` event with the returned `(summary, final_output)`
  once the call returns, catching exceptions into an `"error"` event —
  the same shape the original implementation used, so the event-consuming
  UI loop needed no structural changes.
- Removed the three separate model-override dropdowns' "Judge model"
  option entirely: `run.py`'s `_role_model()` only supports two override
  buckets (`model_main` for builder/fixer/judge/synthesizer, `model_fast`
  for supervisor/planner/critic) — there was never a real judge-specific
  override path in the shared pipeline, so the UI now offers exactly what
  the CLI actually supports, nothing more.
- Removed the "Mode" selectbox that previously **forced** a mode value
  bypassing the Supervisor's own detection (the old code even displayed
  both "Supervisor suggested mode" and "Selected UI mode" side by side —
  a sign the original author already sensed this mismatch). `run_pipeline()`
  has no mode-override parameter by design; mode is always Supervisor-
  detected, matching the CLI exactly (which has never exposed `--mode`).
  Replaced it with a **"Path" selectbox** (`auto`/`fast`/`normal`/`deep`),
  giving real, working parity with the CLI's actual `--path` flag instead
  of a manual mode override that never worked as advertised.
- Fixed the "Fast model" dropdown: removed `gemma3:12b`, which no longer
  appears in any Phase 6 profile (`config/models.yaml`'s `serious`/`coding`
  profiles were consolidated to `llama3.1:8b` for light roles). The "Main
  model" dropdown's options (`qwen2.5:14b`, `qwen2.5-coder:14b`,
  `llama3.1:8b`, `llama3.2:3b`) were already accurate and needed no change.
- **Real cloud status pill**: `render_status_pill("Local only", "green")`
  was hardcoded regardless of config. Now reads
  `orchestrator.cloud_policy.is_cloud_enabled()` and shows "Cloud enabled"
  (dark pill) or "Local only" (green pill) accordingly.
- **Selected path** (Phase 3): shown as a caption in the run summary —
  `` Path selected: `{summary['path']}` ``.
- **Validator failures** (Phase 2): if `summary["metrics"]["validator_failures"]`
  is non-empty, a table of `{rule, times failed}` is shown, with a caption
  explaining that a high Judge score can't rescue a checkable-constraint
  violation.
- **Metrics summary** (Phase 5): a collapsed expander with total runtime,
  a per-agent table (role/model/calls/elapsed_ms), a calls-by-model table
  (the view that visually confirms Phase 6's single-14B-family profiles
  in a real run), and retry/fallback/timeout-event counts — a handful of
  `st.dataframe`/`st.metric` calls, not a charting dashboard.
- **Fallback events** (Phase 4): if `summary["metrics"]["fallbacks"] > 0`,
  a plain warning banner surfaces it rather than leaving a degraded-quality
  run silent.
- **Cloud cost/approval panel** (Phase 7) — see "Scoped tradeoff" below.

## Scoped tradeoff: cloud approval panel is informational only

The guide asks for "the exact payload preview and estimated cost...with an
explicit approve/deny button." This was **deliberately not built as a
functioning control** in this phase, for two concrete, safety-relevant
reasons documented here rather than silently worked around:

1. `orchestrator.cloud_policy.request_human_approval()` blocks on a real
   terminal `input()` call. Calling it from a Streamlit background thread
   (which has no attached interactive terminal — the user interacts via a
   browser, not stdin) would hang indefinitely or raise unpredictably in
   different server environments. Building a *correct* mid-run pause/
   resume flow (the background thread blocks, the UI renders an
   approve/deny button, a click triggers a full Streamlit script rerun
   that must recognize "we're mid-approval" and signal the paused thread)
   requires session-state-coordinated concurrency infrastructure that is
   a substantially larger feature than "expose a UI control" — it's closer
   to a phase of its own.
2. Even a fully-built approval UI would currently terminate in
   `AnthropicAdapter.call()` raising `NotImplementedError` regardless (see
   the Phase 7 report), since the real adapter is still deliberately
   deferred pending model/pricing verification. Building real mid-run
   approval infrastructure for a call that cannot succeed yet is
   effort spent for a stub.

Instead: the run summary shows an informational note when
`cloud_policy.is_cloud_enabled()` is true, explaining exactly why the UI
doesn't attempt escalation and pointing at the CLI's `--allow-cloud` flag
for actual (terminal-based, already fully gated) use. `allow_cloud` is
never set to `True` from the Streamlit UI in this phase — cloud escalation
is not reachable via the dashboard at all, which is the safe default given
`cloud.enabled: false` ships by default anyway. This is a real, working
UI equivalent of "the CLI-flag condition needs a corresponding UI control,
not silent bypassing" (the guide's own troubleshooting note) — the "UI
control" here is the informational message plus the absence of any
button that could trigger the unsafe blocking path, rather than a
non-functional or dangerous approve/deny button.

## Tests added / updated

- `tests/test_pipeline_routing.py::test_run_pipeline_invokes_on_step_callback_for_agent_calls_and_loop_events`
  (new) — confirms `run_pipeline()` called with `on_step` actually fires
  `step` events for every agent (supervisor through synthesizer, including
  critic/fixer in the normal path), that a `step`/`done` event's `output`
  matches the real agent return value, and that `loop_start`/`loop_result`
  events fire with the expected `iteration`/`passed` fields. This is the
  test the guide asks for: proof `run_pipeline()` "still works correctly
  when called with a callback, not just when run standalone from `main()`."
- All 146 pre-existing tests pass unmodified, confirming the `on_step`
  refactor is fully backward compatible (default `None` preserves exact
  prior CLI behavior).
- `python -c "import app.streamlit_app"` (the guide's required smoke test)
  passes with exit code 0.

## Tests run

```
ruff check .                        → All checks passed!
pytest tests/ -v                    → 147 passed
python -c "import app.streamlit_app" → exit 0 (only expected
                                         "missing ScriptRunContext" bare-mode
                                         warnings, no import errors)
```

## Manual UI verification — not performed live in this session

This unattended session runs in a sandboxed environment without outbound
network/port access (confirmed: a `curl localhost` check to verify the
Streamlit server boots was denied by the sandbox). The guide's
`streamlit run app/streamlit_app.py` manual-launch step and its "glance
test" for visual clutter could not be performed live here. In its place:
the full diff was manually re-read end to end for correctness (event
shapes match exactly between `run.py`'s emitted events and the UI's
existing event-consuming loop, which needed no changes to its `if etype
== ...` branches), the import smoke test confirms the module loads
without error, and the full test suite (including the new `on_step`
callback test) passes. A human should still do a real
`streamlit run app/streamlit_app.py` pass before relying on this
day-to-day, per the guide's own verification checklist.

## Files changed

- `app/streamlit_app.py` (535 deletions, ~260 net lines changed — the
  duplicated pipeline implementation removed, new UI elements added)
- `run.py` (70 lines added — `on_step` parameter threaded through, no
  behavior change when omitted)
- `tests/test_pipeline_routing.py` (new `on_step` callback test)
- `docs/audits/2026-07-04-phase-8-maintainer-report.md` (new)

## Remaining risks / TODOs

- Interactive cloud approval in the UI remains unimplemented (see "Scoped
  tradeoff" above) — a real implementation would need Streamlit
  session-state-based pause/resume infrastructure, and should probably
  wait until `AnthropicAdapter.call()` itself is implemented (Phase 7's
  deferred item), so the two land together rather than building UI for a
  call that can't succeed yet.
- No live browser verification was performed in this session (sandboxed,
  no network access) — flagged above as a follow-up for a human to
  confirm before treating the dashboard as production-ready.
- The Streamlit app now imports `run.py` as a module. `run.py`'s own
  `if __name__ == "__main__":` guard means this is safe (no CLI argument
  parsing or `main()` execution happens on import), confirmed by the
  passing import smoke test.

## Commit

```
refactor: unify Streamlit app on run.py's pipeline and surface path/validator/metrics/cloud status
```
