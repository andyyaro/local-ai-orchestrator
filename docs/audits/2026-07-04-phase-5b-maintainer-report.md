# Phase 5b Maintainer Report — Wire Real Resilience Events into Metrics

## Gap being closed

Phase 4 (resilience) and Phase 5 (metrics) each landed independently and were
individually well tested, but `orchestrator/resilience.py`'s
`call_with_resilience()` already accepted an optional `metrics` parameter
that nothing ever passed. `agents/base_agent.py`'s `call_model()` called
`call_with_resilience()` without forwarding any metrics object, and
`run.py`'s `run_pipeline()` never gave the agents it constructs
(`SupervisorAgent`, `PlannerAgent`, `BuilderAgent`, `CriticAgent`,
`FixerAgent`, `JudgeAgent`, `SynthesizerAgent`) a reference to the run's
`RunMetrics` instance. As a result, `run_summary.json`'s
`metrics.retries`, `metrics.fallbacks`, and `metrics.timeout_events` were
always `0` on real runs, even when retries/fallbacks/timeouts genuinely
occurred — the counting logic itself (`RunMetrics.record_retry` etc.) was
correct and unit-tested, but nothing ever called it outside of tests.

## Fix

1. `agents/base_agent.py`: `BaseAgent.__init__` now accepts an optional
   `metrics=None` parameter and stores it as `self.metrics`. `call_model()`
   passes `metrics=self.metrics` into `call_with_resilience()` instead of
   omitting the argument (which silently defaulted to `None`).
2. `run.py`: every agent constructed in `run_pipeline()` now receives
   `metrics=metrics` — the same `RunMetrics(run_dir.name)` instance already
   used for `record_agent_call`, `record_path`,
   `record_validator_failure`, and `record_hard_fail`. No new instance is
   created; this is the same object that gets `finalize()`d into
   `summary["metrics"]`.

Because every agent subclass (`SupervisorAgent`, `PlannerAgent`, etc.)
already forwards `**kwargs` to `BaseAgent.__init__`, no other agent file
needed to change.

## Files changed

- `agents/base_agent.py` — accept and forward `metrics`.
- `run.py` — pass `metrics=metrics` when constructing each of the 7 agents.
- `tests/test_base_agent.py` (new) — proves `call_model()` threads
  `self.metrics` into `call_with_resilience()`, and that it defaults to
  `None` (not a crash) when no metrics object was supplied.
- `tests/test_resilience.py` — added 4 tests using a real `RunMetrics`
  instance (not a stub) to prove `call_with_resilience()`'s existing
  `record_retry` / `record_fallback` / `record_timeout_event` calls
  actually increment the counters that land in `finalize()`'s output, for
  the connection-retry, timeout-fallback, and timeout-with-failed-fallback
  cases, plus a `metrics=None` no-op case.
- `tests/test_pipeline_routing.py` — added one end-to-end regression test,
  `test_pipeline_records_real_resilience_events_in_run_summary`, that
  leaves `BuilderAgent.run()` un-mocked (unlike the existing routing
  tests) so its `call_model()` call really goes through
  `call_with_resilience()`, with a fake adapter that raises
  `ModelConnectionError` once then succeeds. This is the test that would
  have caught the original gap: it asserts
  `summary["metrics"]["retries"] == 1` after a full `run_pipeline()` call,
  which fails without the `agents/base_agent.py` and `run.py` changes
  above.

## Tests run

```
ruff check .                        → All checks passed!
pytest tests/test_metrics.py -v     → 8 passed
pytest tests/test_resilience.py -v  → 18 passed (10 pre-existing + 8 new)
pytest tests/ -v                    → 86 passed
```

## Verification of the original claim

Before this fix, `test_pipeline_records_real_resilience_events_in_run_summary`
(run against the pre-fix code, manually, during investigation) failed with
`summary["metrics"]["retries"] == 0` despite the fake adapter raising a
`ModelConnectionError` on the first call — confirming the reported gap was
real and reproducible, not just a documentation note. After wiring
`metrics` through `BaseAgent` and `run.py`, the same test passes with
`retries == 1`.

## Remaining risks / follow-ups

- None identified within this phase's scope. The wiring is purely additive
  (an optional constructor parameter with a `None` default) and does not
  change any agent's behavior, model selection, or control flow.
- Phase 6 is out of scope for this change and was not started.

## Commit

```
fix: wire resilience events into run metrics
```
