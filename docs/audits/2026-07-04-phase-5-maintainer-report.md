# Phase 5 Maintainer Report — Metrics and Profiling

Date: 2026-07-04
Source guide: `docs/upgrade-guide/10-phase-5-metrics.md`

## Phase name

Phase 5 — Metrics and Profiling

## Branch

```text
phase-5-metrics
```

## Files changed

```text
orchestrator/metrics.py         (new: RunMetrics collector — record_agent_call,
                                  record_path, record_retry, record_fallback,
                                  record_timeout_event, record_validator_failure,
                                  record_hard_fail, finalize())
orchestrator/resilience.py       (call_with_resilience() accepts an optional
                                  metrics param; reports retries/fallbacks/
                                  timeout events)
run.py                           (instantiates RunMetrics per run, threads it
                                  through _log_agent_call(), records path/
                                  validator-failures/hard-fails, finalizes into
                                  summary["metrics"])
tests/test_metrics.py             (new)
tests/test_pipeline_routing.py    (extended to assert run_summary.json's
                                   "metrics" key for both fast and normal paths)
```

## Commit SHA

`a53f073` — "feat: add run metrics collection and aggregation into
run_summary.json" (squashed into main as `e561fd4` via PR #7)

## PR URL

https://github.com/andyyaro/local-ai-orchestrator/pull/7

## GitHub Actions result

`lint-and-test` — **pass** (both matrix jobs, ~32-37s each)

## Tests run

```bash
ruff check .
pytest tests/test_metrics.py -v
pytest tests/ -v
```

## Local test result

- `ruff check .` — all checks passed
- `tests/test_metrics.py` — 8/8 passed: per-agent aggregation across repeated
  calls to the same role, `calls_by_model` grouping across distinct models,
  each `record_*` method's effect on `finalize()`, and a zero-events case
  producing a clean, well-formed summary with zeroed counts
- Full `tests/` suite — **79/79 passed**
- `tests/test_pipeline_routing.py` was extended (not just left as Phase 3
  coverage) to assert `run_summary.json`'s `"metrics"` key is well-formed for
  both the fast path (planner/critic/fixer absent from `per_agent`, judge
  called once) and the normal path (planner/critic/fixer each called once,
  `total_elapsed_ms` present) — this exercises the guide's manual verification
  step ("a manual pipeline run produces a run_summary.json with a metrics
  key...") at the automated-test level instead of a live Ollama run.

## Merge result

Squash-merged via `gh pr merge 7 --squash --delete-branch`. Fast-forwarded
cleanly, no conflicts.

## Branch deletion result

Remote `phase-5-metrics` deleted automatically by `--delete-branch`. Local
branch was also removed as part of the same operation; stale
remote-tracking ref cleaned up with `git remote prune origin`.

## Final git status

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Branches: `main` only (local and remote), tracking `e561fd4`.

## Risks or TODOs

- `RunMetrics` is wired into `run.py` (the terminal pipeline) but **not**
  into `run_langgraph.py` / `orchestrator/graph.py` — the guide's file list
  for this phase only named `orchestrator/metrics.py`, `tests/test_metrics.py`,
  `run.py`, and `orchestrator/resilience.py`, so the LangGraph pipeline still
  has no metrics collection. This mirrors the same gap already noted in the
  Phase 3 report for routing on that entrypoint.
- `call_with_resilience()`'s new `metrics` parameter is plumbed and unit
  tested directly, but real agent calls still don't pass a `RunMetrics`
  instance through — `agents/base_agent.py`'s `call_model()` wasn't in this
  phase's file scope (same gap already flagged in the Phase 4 report), so
  `retries`/`fallbacks`/`timeout_events` will read as `0` in a real run today
  even though the counting logic itself is correct and tested with a fake
  adapter. Wiring `call_model()` to accept and forward a metrics object is
  the natural follow-up once a phase touches `agents/base_agent.py` again.
- No live Ollama run was performed to visually inspect a real `run_summary.json`
  with populated `calls_by_model` (e.g. seeing the actual model-swap pattern
  across `qwen2.5:14b`/`gemma3:12b`/`phi4:14b` in the `serious` profile) — this
  was validated at the pipeline-test level with mocked agents instead, for
  the same "no live model calls authorized in this session" reason noted in
  the Phase 3 and Phase 4 reports. The aggregation logic itself is exercised
  end-to-end through `run_pipeline()` in `tests/test_pipeline_routing.py`.

## Deviations from the guide

- None beyond what's noted above as scope gaps (both already flagged and
  accepted in the Phase 3/4 reports for the same reason: the guide's own file
  lists didn't include `run_langgraph.py` or `agents/base_agent.py` for this
  phase, so they were left untouched per the "don't modify files outside
  scope" instruction).
- Validator-failure and hard-fail recording (`record_validator_failure`,
  `record_hard_fail`) was placed at the two Judge call sites in `run.py`
  (fast path and normal loop) rather than inside
  `orchestrator/validators.py`'s `apply_validator_results_to_verdict()`
  itself — this keeps `orchestrator/validators.py` (not in this phase's file
  list) untouched and keeps `RunMetrics` reporting centralized at the one
  place in `run.py` that already has both the validator results and the
  final verdict in scope.

## Safe to start next phase?

Phase 6 (memory discipline / model-swap elimination) is explicitly out of
scope for this session per the hard stop instructions ("Do not start Phase
6. Do not start any v2.0 phase."). All three requested phases (3, 4, 5) are
now merged to main, tests are green, GitHub Actions is green, and the working
tree is clean. This is the final stopping point for this session.
