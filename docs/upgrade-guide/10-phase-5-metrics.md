# 10 — Phase 5: Metrics and Profiling

## Goal

Measure runtime, model choice, routing path, retry/fallback events, and
validator outcomes for every run, and aggregate them into `run_summary.json`
so every later change (routing, timeouts, model profiles) can be proven to
help or not — not just assumed to.

## Why it matters

`orchestrator/logger.py` already writes structured JSON events
(`agent_start`, `agent_end` with `elapsed_ms`, `score`, `code_verification`,
`run_stop`, `error`) to `logs/pipeline.log`. That's real, working
instrumentation — but nothing aggregates it. Right now, to answer "did Phase
3's routing actually make runs faster," you'd have to manually grep
`logs/pipeline.log` and do arithmetic by hand. This matters because every
phase from here forward (and Phase 3/4 specifically) makes a measurable
claim — fewer calls, fewer retries, less swapping — and a claim you can't
verify with a number is just a guess.

This phase does not replace the existing logger. It adds a collector that
sits alongside it during a run and produces one aggregated summary at the
end, reusing exactly the same per-agent timing data `_log_agent_call()` in
`run.py` already computes.

## Files likely touched

```text
orchestrator/metrics.py   (new)
tests/test_metrics.py     (new)
run.py                     (instantiate collector, record events, save into run_summary.json)
orchestrator/resilience.py (report retry/fallback/timeout events, if Phase 4 already landed)
```

Files to inspect first (read-only):

```text
orchestrator/logger.py
run.py
orchestrator/router.py
orchestrator/resilience.py
orchestrator/validators.py
```

Note: this phase assumes Phase 3 (routing) and Phase 4 (resilience) have
already landed, since it collects the path and retry/fallback data they
produce. If either hasn't landed yet, implement the metrics collector to
accept whatever data is currently available and add the missing fields as
`None`/`0` with a clear comment — don't block this phase entirely on the
others being done first.

Streamlit display of these metrics (charts, tables) is explicitly deferred
to Phase 8 (`13-phase-8-streamlit-updates.md`, planned) — this phase only
needs the data to exist and be correct in `run_summary.json`, not to be
pretty in the UI. Note this overlap so you don't expect a UI change here.

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-5-metrics
```

2. Create `orchestrator/metrics.py` with a single collector class used for
   the lifetime of one run:

   - `class RunMetrics:` constructed once per run (`RunMetrics(run_id)`).
   - `record_agent_call(role: str, model: str, elapsed_ms: int)` — called
     from `_log_agent_call()` in `run.py`, right next to the existing
     `log.agent_end(...)` call, so timing is captured from the same
     measurement, not a second one.
   - `record_path(path: str)` — called once, right after Phase 3's
     `classify_path()` result is known.
   - `record_retry(role: str, model: str, failure_type: str)` — called from
     Phase 4's `call_with_resilience()` whenever a retry happens.
   - `record_fallback(role: str, from_model: str, to_model: str)` — called
     from `call_with_resilience()` whenever a fallback-to-smaller-model
     happens.
   - `record_timeout_event(role: str, model: str)` — called whenever a
     `ModelTimeoutError` is classified, regardless of whether it led to a
     retry or fallback.
   - `record_validator_failure(rule: str)` — called from
     `_apply_validator_results_to_verdict()` for each failing rule.
   - `record_hard_fail(reason: str)` — called wherever a hard fail is
     appended to a verdict (`broken_code`, `constraint_violation`, or a
     Judge-reported one).
   - `finalize(total_elapsed_ms: int) -> dict` — returns the aggregated
     summary: total runtime, per-agent breakdown (role → model, call count,
     total elapsed ms), calls grouped by model name (this is what will let
     you see model-swap counts at a glance), path selected, retry count,
     fallback count, timeout event count, validator failure counts by rule,
     and hard fail counts by reason.

3. Wire `RunMetrics` into `run.py`'s `run_pipeline()`:
   - Instantiate it near the top, right after `log = get_logger(run_dir.name)`.
   - Call `record_agent_call` inside `_log_agent_call()` alongside the
     existing `log.agent_end()` call — pass the collector in as a parameter
     rather than making it a global, so tests can construct a fresh
     `RunMetrics` per test without import-order issues.
   - Call `record_path` right after path classification (Phase 3).
   - Call `finalize()` right before `summary["run_summary.json"]` is saved,
     and store the result under `summary["metrics"]`.

4. If Phase 4 has already landed, wire `record_retry`/`record_fallback`/
   `record_timeout_event` calls into `orchestrator/resilience.py`'s
   `call_with_resilience()` — this likely means threading an optional
   `metrics: RunMetrics | None = None` parameter through that function so it
   can report events without resilience.py needing to import run.py (which
   would create a circular import). If Phase 4 hasn't landed yet, skip this
   step and note it as a follow-up once Phase 4 exists.

## Tests to add

Create `tests/test_metrics.py` covering:

- `RunMetrics.record_agent_call` followed by `finalize()` produces the
  expected per-agent breakdown and total elapsed time for a few recorded
  calls, including a case with two calls to the *same* role (e.g. two Critic
  calls across two loop iterations) to confirm counts aggregate rather than
  overwrite.
- `finalize()` correctly groups multiple calls to different models (e.g.
  three calls to `"qwen2.5:14b"` and one to `"llama3.2:3b"`) under a
  `calls_by_model` breakdown — this is the field you'll use later to
  visually confirm whether Phase 6 successfully reduced distinct large-model
  usage in one run.
- `record_retry`, `record_fallback`, `record_timeout_event`,
  `record_validator_failure`, and `record_hard_fail` each show up correctly
  in `finalize()`'s output.
- `finalize()` on a `RunMetrics` instance with no recorded events at all
  returns a well-formed dict with zeroed counts, not an error — a fast-path
  run with no retries or fallbacks should still produce a clean summary.

## Commands to run

```bash
ruff check .
pytest tests/test_metrics.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_metrics.py` passes.
- The full `tests/` suite still passes.
- A manual pipeline run produces a `run_summary.json` with a `"metrics"` key
  containing `total_elapsed_ms`, `per_agent`, `calls_by_model`, `path`,
  `retries`, `fallbacks`, `timeout_events`, `validator_failures`, and
  `hard_fails`.

## If it fails

- `calls_by_model` doesn't show the model-swap pattern you expected from a
  real run: double check `record_agent_call` is being passed the *actual*
  resolved model name (post `_role_model()` override resolution), not the
  CLI override string or a placeholder — a common mistake is recording
  `args.model_main` instead of the model that was actually resolved and used
  for that specific role.
- Circular import between `orchestrator/metrics.py` and `orchestrator/resilience.py`:
  keep `RunMetrics` free of any import from `resilience.py` or `adapters.py`
  — it should be a passive data collector that other modules call into, not
  something that imports pipeline internals itself.

## Rollback plan

Metrics collection is purely additive and read-only with respect to pipeline
behavior — it should never change what the pipeline does, only what gets
recorded. If it somehow causes a regression (for example, a forgotten
`metrics.finalize()` call blocking on missing data), revert the phase:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-5-metrics
```

## Commit suggestion

```text
feat: add run metrics collection and aggregation into run_summary.json
```

## Done when

```text
run_summary.json clearly shows what happened and where time was spent: total
runtime, per-agent timing, which models were actually called and how many
times, the selected routing path, and counts of retries, fallbacks, timeout
events, validator failures, and hard fails.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 5: metrics and profiling.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- orchestrator/logger.py
- run.py
- orchestrator/router.py
- orchestrator/resilience.py
- orchestrator/validators.py

Implement the following:
1. Create orchestrator/metrics.py with a RunMetrics class: record_agent_call,
   record_path, record_retry, record_fallback, record_timeout_event,
   record_validator_failure, record_hard_fail, and finalize(total_elapsed_ms)
   returning an aggregated summary dict (total_elapsed_ms, per_agent,
   calls_by_model, path, retries, fallbacks, timeout_events,
   validator_failures, hard_fails).
2. Wire it into run.py's run_pipeline(): instantiate once per run, call
   record_agent_call from _log_agent_call() using the same elapsed_ms
   already computed there, call record_path after path classification, and
   store finalize()'s result under summary["metrics"] before saving
   run_summary.json.
3. If orchestrator/resilience.py already exists (Phase 4 landed), thread an
   optional metrics parameter through call_with_resilience() to report
   retries/fallbacks/timeout events. If resilience.py does not exist yet,
   skip this step and note it as a follow-up.
4. RunMetrics must not import from resilience.py, adapters.py, or run.py —
   it is a passive collector other modules call into.

Create tests/test_metrics.py covering aggregation across multiple calls to
the same role, calls_by_model grouping across different models, each
record_* method's effect on finalize()'s output, and a zero-events case
producing a clean, well-formed summary.

Do not modify any file outside this scope.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_metrics.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Any remaining risks or TODOs (including whether Phase 4 wiring was
   possible or deferred)
4. A suggested commit message
```
