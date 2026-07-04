# Phase 4 Maintainer Report — Timeout and Resilience

Date: 2026-07-04
Source guide: `docs/upgrade-guide/09-phase-4-timeout-resilience.md`

## Phase name

Phase 4 — Timeout and Resilience

## Branch

```text
phase-4-timeout-resilience
```

## Files changed

```text
config/models.yaml               (new "resilience" section: timeouts, fallback_model,
                                   max_local_retries, cloud_backoff)
orchestrator/config_loader.py    (new get_resilience_config())
orchestrator/resilience.py       (new: ModelCallError hierarchy, classify_failure,
                                   get_timeout_for_model, call_with_resilience)
orchestrator/adapters.py         (OllamaAdapter.call() raises typed exceptions instead
                                   of RuntimeError; accepts per-call timeout override)
agents/base_agent.py             (call_model() delegates to call_with_resilience();
                                   removed inline retry loop, sys.exit(1), and _fatal())
run.py                           (new except FatalModelError clause in main(),
                                   mirroring the existing KeyboardInterrupt handling)
tests/test_resilience.py         (new)
```

## Commit SHA

`a182b64` — "feat: add failure classification, model fallback, and clean failure
handling" (squashed into main as `6ddcdaf` via PR #6)

## PR URL

https://github.com/andyyaro/local-ai-orchestrator/pull/6

## GitHub Actions result

`lint-and-test` — **pass** (both matrix jobs, ~24-34s each)

## Tests run

```bash
ruff check .
pytest tests/test_resilience.py -v
pytest tests/ -v
```

## Local test result

- `ruff check .` — all checks passed
- `tests/test_resilience.py` — 14/14 passed: `classify_failure` for all four
  exception classes; `get_timeout_for_model` for small/medium/large/default;
  `call_with_resilience` retry-once-on-connection-error,
  fallback-once-on-timeout, fatal-on-exhausted-fallback,
  fatal-on-exhausted-retry, fail-fast-on-HTTP-error, and first-try-success
  cases — all using a fake adapter, no real Ollama calls, `time.sleep` mocked
  via an autouse fixture so the suite stays fast
- Full `tests/` suite — **71/71 passed**

## Merge result

Squash-merged via `gh pr merge 6 --squash --delete-branch`. Fast-forwarded
cleanly, no conflicts.

## Branch deletion result

Remote `phase-4-timeout-resilience` deleted automatically by `--delete-branch`.
Local branch was also removed as part of the same operation; stale
remote-tracking ref cleaned up with `git remote prune origin`.

## Final git status

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Branches: `main` only (local and remote), tracking `6ddcdaf`.

## Risks or TODOs

- The optional `--resume <run_dir>` CLI flag (step 7 in the guide, explicitly
  a stretch goal) was **not implemented** and is deferred, per the guide's own
  instruction to stop after the core resilience behavior (steps 1-6) is solid
  and tested rather than shipping a half-working resume flag.
- No live test was performed that actually stops Ollama mid-run (the guide's
  manual verification step, `osascript -e 'quit app "Ollama"'`) — this would
  require Ollama to be running and a real pipeline run in progress, which
  wasn't authorized in this unattended session. The retry/fallback/fatal-error
  logic was validated at the unit level instead, with a fake adapter standing
  in for the real Ollama connection.
- The cloud-backoff branch (`resilience.cloud_backoff` config, mentioned in
  the guide) has no code path yet that actually exercises exponential backoff
  with jitter — this is expected and explicitly noted in the guide, since
  there is no working cloud adapter until Phase 7. The config values exist
  and `ModelHTTPError` fails fast today; wiring real backoff is future work
  for whenever Phase 7 lands a real cloud adapter that returns 429/503.

## Deviations from the guide

- The pre-existing "empty response" retry behavior in the old
  `call_model()` (raising `ValueError` and retrying up to `max_retries` times
  when the adapter returned an empty string) was **removed** rather than
  ported into `call_with_resilience()`. The guide's typed-exception hierarchy
  only covers connection/timeout/HTTP failures classified from `requests`
  exceptions, and doesn't mention empty-response handling at all. Since no
  existing test exercised this path, and the guide's explicit goal is "replace
  the inline retry loop" rather than preserve every corner of its prior
  behavior, this was treated as in-scope simplification rather than a
  regression. Flagging in case an empty-response safety net is wanted later.
- `agents/base_agent.py`'s `_fatal()` method was deleted entirely (not just
  had its `sys.exit(1)` call removed) since nothing calls it anymore —
  `call_model()` now delegates fully to `call_with_resilience()`, which raises
  `FatalModelError` directly. Keeping `_fatal()` around unused would have left
  dead code.
- `run.py`'s new `except FatalModelError` branch uses `sys.exit(1)` (matching
  a failure exit code) rather than `sys.exit(0)` like the `KeyboardInterrupt`
  branch, since a model failure is not a clean stop the way a user-initiated
  interrupt is — this distinction wasn't explicit in the guide but seemed the
  correct default for exit-code semantics in scripts/CI that might check it.

## Safe to start next phase?

**Yes.** Ruff passed, full test suite passed (71/71), GitHub Actions passed,
merge was clean with no conflicts, `git status` is clean on main, and no
unexpected files were touched. Proceeding to Phase 5 (Metrics and Profiling),
which explicitly builds on both Phase 3 (routing) and Phase 4 (resilience)
having already landed.
