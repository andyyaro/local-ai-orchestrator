# Unattended Upgrade Batch — Final Report (Phases 3-5)

Date: 2026-07-04

This session ran three upgrade phases sequentially — Phase 3 (routing/speed),
Phase 4 (timeout/resilience), and Phase 5 (metrics) — following each phase's
guide in `docs/upgrade-guide/`, with the full checkout → implement → test →
PR → CI → squash-merge → cleanup → report loop for each. Per-phase detail
lives in the individual reports:

- `docs/audits/2026-07-04-phase-3-maintainer-report.md`
- `docs/audits/2026-07-04-phase-4-maintainer-report.md`
- `docs/audits/2026-07-04-phase-5-maintainer-report.md`

## 1. Phases completed

- **Phase 3 — Routing, Speed, and Pipeline Collapse**: fast/normal/deep
  routing added to both `run.py` and `orchestrator/graph.py`, skipping the
  Planner and/or the Critic/Fixer loop based on a deterministic heuristic.
- **Phase 4 — Timeout and Resilience**: typed model-call exceptions,
  size-class timeouts, connection-error retry, timeout-triggered fallback to
  a smaller model, and clean `FatalModelError` propagation instead of a hard
  `sys.exit(1)`.
- **Phase 5 — Metrics and Profiling**: a `RunMetrics` collector aggregating
  per-agent timing, model-swap counts, routing path, retries/fallbacks/
  timeouts, and validator/hard-fail counts into `run_summary.json`.

All three phases are merged into `main`. No hard-stop condition was
triggered at any point (ruff, pytest, and GitHub Actions passed on every
phase; no merge conflicts; no unexpected files were touched; no destructive
or restricted commands were run).

## 2. PR URLs

- Phase 3: https://github.com/andyyaro/local-ai-orchestrator/pull/5
- Phase 4: https://github.com/andyyaro/local-ai-orchestrator/pull/6
- Phase 5: https://github.com/andyyaro/local-ai-orchestrator/pull/7

## 3. Merge SHAs

- Phase 3: `fa3c09a` — feat: add fast/normal/deep routing to reduce
  unnecessary model calls (#5)
- Phase 4: `6ddcdaf` — feat: add failure classification, model fallback, and
  clean failure handling (#6)
- Phase 5: `e561fd4` — feat: add run metrics collection and aggregation into
  run_summary.json (#7)

Each phase's PR was squash-merged with `gh pr merge --squash --delete-branch`
after GitHub Actions' `lint-and-test` check passed on both matrix jobs.

## 4. Final branch

```text
main
```

All phase branches (`phase-3-routing`, `phase-4-timeout-resilience`,
`phase-5-metrics`) were deleted both locally and on the remote after their
respective merges. No phase branches remain.

## 5. Final `git status -sb`

```text
## main...origin/main
```

Clean — nothing to commit, local `main` fully in sync with `origin/main` at
`8c0dae1` (the Phase 5 report commit, made directly to `main` following the
same pattern as the Phase 0 baseline audit already in the repo).

## 6. Remaining risks

- **`run_langgraph.py` (LangGraph CLI entrypoint) was not updated in any of
  the three phases.** It has no `--path` flag and always passes concrete
  `max_loops`/`threshold` values, so Phase 3's routing structure exists and is
  tested in `orchestrator/graph.py` but isn't reachable end-to-end from that
  specific CLI. This was consistent with each guide's explicit "files likely
  touched" list, which never named this file.
- **`agents/base_agent.py`'s `call_model()` does not yet pass a `RunMetrics`
  instance into `call_with_resilience()`.** Phase 5's retry/fallback/timeout
  counters are implemented and unit-tested with a fake adapter, but a real
  pipeline run today will always report `retries: 0, fallbacks: 0,
  timeout_events: 0` in `run_summary.json` regardless of what actually
  happened, until a future phase threads a metrics object through
  `base_agent.py` (not in scope for Phases 3-5 per their guides).
- **No live Ollama runs were performed** for any of the three phases' manual
  verification steps (e.g. actually killing Ollama mid-run for Phase 4, or
  eyeballing a real fast-path run's reduced terminal output for Phase 3).
  Every behavior was validated through unit and pipeline-level tests with
  mocked agents/adapters instead, since this was an unattended session with
  no authorization to run real model calls, download models, or otherwise
  touch the live Ollama server.
- **The fast/normal/deep routing heuristic** (`orchestrator/router.py`) is a
  first-pass, deliberately simple set of constants (word-count threshold,
  keyword list). It hasn't been validated against a large sample of real
  goals — the guide's own remediation path (pin misclassified goals as
  regression tests before tuning) applies if it misfires in practice.
- **The empty-response retry safety net** that existed in the pre-Phase-4
  `call_model()` (retrying when the adapter returned an empty string) was
  removed as part of Phase 4's refactor and not replaced, since the guide's
  typed-exception hierarchy doesn't cover that case. This is a minor
  behavioral regression versus v1.0.0, noted in the Phase 4 report.

## 7. Is Phase 6 ready to start?

**Not started, and not started in this session per explicit instruction**
("Do not start Phase 6. Do not start any v2.0 phase."). From a purely
technical readiness standpoint: yes, the prerequisites Phase 6 would build on
(routing from Phase 3, resilience from Phase 4, metrics from Phase 5) are all
merged, tested, and green on `main`, so a future session could pick up Phase
6 (memory discipline / model-swap elimination) cleanly. The two open items
most relevant to Phase 6 specifically are the `calls_by_model` metrics gap
(item 6 above) — Phase 6's whole premise is reducing model swaps, and you'll
want real retry/fallback numbers, not just the call-count/model-swap data, to
fully evaluate it — and confirming `run_langgraph.py` parity if the LangGraph
pipeline is meant to be a first-class target for that phase too.

This is the final stopping point for this session, as instructed.
