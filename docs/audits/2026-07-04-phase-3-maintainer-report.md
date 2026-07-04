# Phase 3 Maintainer Report — Routing, Speed, Pipeline Collapse

Date: 2026-07-04
Source guide: `docs/upgrade-guide/08-phase-3-routing-speed.md`

## Phase name

Phase 3 — Routing, Speed, and Pipeline Collapse

## Branch

```text
phase-3-routing
```

## Files changed

```text
config/models.yaml               (new "paths" section: fast/normal/deep)
orchestrator/config_loader.py    (new get_path_settings())
orchestrator/router.py           (new: classify_path, get_path_config)
orchestrator/logger.py           (new path_selected() method)
orchestrator/state.py            (new PipelineState fields: path, path_override,
                                   skip_planner, skip_critic_fixer_loop)
orchestrator/graph.py            (conditional edges: route_after_supervisor,
                                   route_after_builder, updated route_after_judge;
                                   node_builder/node_judge fall back to
                                   refined_goal/draft when planner/critic/fixer skipped)
run.py                           (--path CLI flag, path selection after Supervisor,
                                   conditional Planner skip, conditional single-Judge
                                   fast path, path recorded in run_summary.json)
tests/test_router.py             (new)
tests/test_pipeline_routing.py   (new)
```

## Commit SHA

`d9b7517` — "feat: add fast/normal/deep routing to reduce unnecessary model calls"
(squashed into main as `fa3c09a` via PR #5)

## PR URL

https://github.com/andyyaro/local-ai-orchestrator/pull/5

## GitHub Actions result

`lint-and-test` — **pass** (both matrix jobs, ~31-34s each)

## Tests run

```bash
ruff check .
pytest tests/test_router.py -v
pytest tests/ -v
```

## Local test result

- `ruff check .` — all checks passed
- `tests/test_router.py` — 9/9 passed (classify_path fast/deep/normal/override cases,
  get_path_config for all three paths)
- `tests/test_pipeline_routing.py` — 2/2 passed (fast path skips Planner artifact
  and Critic/Fixer calls; normal path still runs Planner + one Critic/Fixer loop)
- Full `tests/` suite — **57/57 passed**
- Sanity check: `orchestrator.graph.build_graph()` still compiles with the new
  conditional edges (verified via direct import, not part of pytest)

## Merge result

Squash-merged via `gh pr merge 5 --squash --delete-branch`. Fast-forwarded
cleanly, no conflicts.

## Branch deletion result

Remote `phase-3-routing` deleted automatically by `--delete-branch`. Local
branch was also removed as part of the same operation (confirmed via
`git branch -a`); stale remote-tracking ref cleaned up with
`git remote prune origin`.

## Final git status

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Branches: `main` only (local and remote), tracking `fa3c09a`.

## Risks or TODOs

- The fast-path heuristic (`FAST_PATH_WORD_THRESHOLD = 25`, keyword list in
  `orchestrator/router.py`) is a first-pass judgment call, per the guide's own
  instruction to pin it in code rather than tune by trial and error. If a real
  run misclassifies, the guide's own remediation applies: add the exact goal
  string as a regression test in `tests/test_router.py` before adjusting
  thresholds/keywords.
- `run_langgraph.py` (the CLI entry point for the LangGraph pipeline) was
  **not** modified — it still passes concrete `max_loops`/`threshold` defaults
  rather than `None`-able CLI flags, and has no `--path` flag. This means the
  new routing structure in `orchestrator/graph.py` is real and tested via
  `build_graph()`, but is not yet reachable end-to-end from that specific CLI.
  This file was outside the guide's explicit "files likely touched" list, so
  it was left untouched per the "do not modify any file outside this scope"
  instruction. Flagging as a follow-up if the LangGraph CLI needs the same
  `--path` UX as `run.py`.
- No live Ollama run was performed to visually confirm "fewer steps printed to
  the terminal" for a real fast-path run (the guide's manual verification
  step) — this was validated at the unit/pipeline-test level with mocked
  agents instead, since no destructive or long-running model calls were
  authorized in this session.

## Deviations from the guide

- `log.run_start(...)` was moved to fire *after* path classification (instead
  of as the very first call in `run_pipeline()`) so it could log the
  *effective* `max_loops`/`threshold` (path-resolved or CLI-overridden)
  instead of the pre-path-selection placeholder values. This is a minor
  reordering, not a behavior change the guide prohibits.
- `--max-loops`/`--threshold` CLI defaults were changed from concrete integers
  (`3`/`70`) to `None`, so `run_pipeline()` can distinguish "user explicitly
  passed a value" from "let the path decide" per the guide's explicit
  requirement ("CLI flags you type yourself should still win over the path's
  defaults"). This was necessary to implement the override behavior correctly;
  the guide's own file list anticipated this change in `run.py`.
- Added a second pipeline-level test (`test_normal_path_runs_planner_and_critic_fixer_loop`)
  beyond the minimum the guide asked for, to lock in that the *non*-fast paths
  still exercise Planner/Critic/Fixer — this guards against a routing
  regression accidentally collapsing the normal/deep paths too.

## Safe to start next phase?

**Yes.** All hard-stop conditions were clear: ruff passed, full test suite
passed (57/57), GitHub Actions passed, merge was clean with no conflicts,
`git status` is clean on main, and no unexpected files were touched. Proceeding
to Phase 4 (Timeout and Resilience).
