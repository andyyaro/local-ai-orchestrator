# 08 — Phase 3: Routing, Speed, and Pipeline Collapse

## Goal

Reduce unnecessary model calls and speed up normal runs by routing tasks to a
fast, normal, or deep path instead of always running the full 7-agent
pipeline with the same loop count.

## Why it matters

The 12m49s runtime came from two compounding causes, both confirmed by direct
repo inspection and by both research reports: too many sequential model calls
per run, and swapping between different 14B-class models mid-run. A single
run with `max_loops = N` makes `3 + 4N` sequential model calls today
(Supervisor, Planner, Builder, then Critic+Fixer+Judge per loop, plus
Synthesizer). At `N = 4` that's 19 blocking calls — for a task that may not
have needed a full plan-critique-fix-judge cycle at all.

This matters because a simple task ("summarize this in 100 words") does not
need the same pipeline depth as a complex one ("write a Python module with
tests and handle five edge cases"). Forcing every task through the full
7-agent loop is the single biggest reason normal runs feel slow. This phase
does not touch *which* models are used (that's Phase 6's job) — it touches
*how many agent calls happen* and *how many loop iterations run*, based on
how complex the task actually is.

Model-swap elimination (avoiding alternating between `qwen2.5:14b`,
`qwen2.5-coder:14b`, and `phi4:14b` within one run) is a related but separate
problem, owned by Phase 6 (`11-phase-6-memory-discipline.md`, planned). This
phase only reduces *call count and loop count* — note the overlap so you
don't expect this phase alone to fully fix the 12m49s runtime; it fixes the
"too many calls" half, Phase 6 fixes the "swapping too many different models"
half.

## Files likely touched

```text
orchestrator/router.py   (new)
tests/test_router.py     (new)
run.py                    (wire in path selection, skip agents based on path)
orchestrator/graph.py     (same wiring, LangGraph pipeline)
config/models.yaml        (add a "paths" section)
```

Files to inspect first (read-only):

```text
run.py
orchestrator/graph.py
orchestrator/config_loader.py
config/models.yaml
config/modes.yaml
orchestrator/logger.py
```

As with every prior phase, check whether `run.py` and `orchestrator/graph.py`
have already drifted apart (Phase 0 should have already surfaced this) before
wiring the same logic into both.

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-3-routing
```

2. Add a `paths` section to `config/models.yaml`, alongside the existing
   `profiles` section. This defines what each path actually changes about
   pipeline shape — not which models are used, just how much of the
   pipeline runs:

```yaml
paths:
  fast:
    skip_planner: true
    skip_critic_fixer_loop: true
    max_loops: 1
    threshold: 60
  normal:
    skip_planner: false
    skip_critic_fixer_loop: false
    max_loops: 2
    threshold: 70
  deep:
    skip_planner: false
    skip_critic_fixer_loop: false
    max_loops: 4
    threshold: 80
```

   Add corresponding getters to `orchestrator/config_loader.py`
   (`get_path_settings(path_name: str) -> dict`), following the same
   caching pattern already used for `load_models_config()`.

3. Create `orchestrator/router.py` with a single, deterministic
   classification function — no model call, just heuristics on the goal
   text and mode:

   - `classify_path(goal: str, mode: str, override: str | None = None) -> str`
     Returns `"fast"`, `"normal"`, or `"deep"`. If `override` is given (from
     a new `--path` CLI flag), return it directly without running any
     heuristic — this is what lets you force a path for testing or for a
     task you already know is simple or complex. Otherwise:
     - Short goals (for example, under ~25 words) with no complexity
       signal → `"fast"`.
     - Goals containing explicit complexity language ("comprehensive",
       "thorough", "in-depth", "step by step", "with tests", "handle edge
       cases") or `mode in {"coding", "debugging"}` → `"deep"`.
     - Everything else → `"normal"`.
     Document the exact thresholds and keyword list you pick as constants
     at the top of the file, since these are judgment calls you're making
     once in code rather than leaving to per-run guessing.

   - `get_path_config(path: str) -> dict`
     Thin wrapper around `config_loader.get_path_settings(path)`.

4. Wire path selection into `run.py`'s `run_pipeline()`:
   - Add a `--path` CLI argument (`choices=["auto", "fast", "normal",
     "deep"]`, default `"auto"`) to `main()`.
   - After the Supervisor step (which already determines `mode`), call
     `classify_path(refined_goal, mode, override=None if args.path == "auto" else args.path)`.
   - Store the selected path in `summary["path"]` and log it via a new
     `log.path_selected(path)` entry in `orchestrator/logger.py` (add this
     method next to the existing `run_start`/`agent_start` methods).
   - If `skip_planner` is true for the selected path, skip the Planner step
     entirely and pass the refined goal directly to the Builder as the plan
     (do not call the Planner agent at all — this is a real call
     elimination, not a shortcut plan string).
   - If `skip_critic_fixer_loop` is true, run the Builder's draft straight to
     a single Judge call (no Critic, no Fixer) and treat that as the only
     iteration — still apply Phase 2's validators and, in coding mode, code
     verification, before the Judge call, exactly as the full pipeline does.
   - Use the path's `max_loops` and `threshold` as the effective values
     unless the caller explicitly passed `--max-loops` / `--threshold` on
     the command line — CLI flags you type yourself should still win over
     the path's defaults, since you may be intentionally overriding for a
     specific run.

5. Mirror the same path-based branching in `orchestrator/graph.py` — this
   means adding conditional edges so `node_supervisor` can route directly to
   `node_builder` (skipping `node_planner`) and so `node_builder` can route
   directly to `node_synthesizer` (skipping the Critic/Fixer/Judge loop
   entirely) when the fast path applies. This is a real structural change to
   the graph, not just a state flag — take care that `build_graph()`'s
   conditional edges correctly express "fast path skips planner" and "fast
   path does a single judge check with no loop," matching what `run.py` does.

## Tests to add

Create `tests/test_router.py` covering:

- `classify_path` returns `"fast"` for a short, plain goal with no
  complexity keywords.
- `classify_path` returns `"deep"` for a goal containing a complexity
  keyword, and separately for `mode == "coding"`.
- `classify_path` returns `"normal"` for a goal that matches neither fast
  nor deep signals.
- `classify_path` returns exactly the `override` value when one is given,
  regardless of what the heuristic would otherwise pick.
- `get_path_config` returns the exact `max_loops`/`threshold`/skip flags
  from `config/models.yaml`'s `paths` section for each of the three paths.

Update or add pipeline-level tests confirming that when the fast path is
selected, the Planner agent is not invoked and no `01_planner_plan.txt`
artifact is written, and the Critic/Fixer agents are not invoked for a
single-iteration fast-path run.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_router.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_router.py` passes.
- The full `tests/` suite still passes.
- A manual fast-path run completes with visibly fewer steps printed to the
  terminal (no `STEP 2 — PLANNER`, no `LOOP 1/1 — CRITIC → FIXER`), and
  `run_summary.json` records `"path": "fast"`.
- A manual deep-path run still behaves exactly like a full v1.0.0 run today.

## If it fails

- `classify_path` misclassifies a goal you actually tried: add that exact
  goal string as a new test case first, then adjust the keyword list or
  length threshold — don't tune the heuristic by trial and error without a
  pinned regression test.
- The fast path skips the Planner but the Builder agent errors because it
  expected a real plan string: check `agents/builder.py`'s prompt template —
  it likely assumes a plan was generated; passing the refined goal directly
  as the "plan" needs to actually make sense to the Builder's prompt, so
  read `prompts/builder.txt` before assuming this wiring is a one-line
  change.
- `orchestrator/graph.py`'s conditional edges produce an invalid graph (for
  example, a node with no outgoing edge for some path): re-check
  `route_after_judge` and add the equivalent routing function for the new
  fast-path branch rather than hardcoding a shortcut inside a single node.

## Rollback plan

If routing produces worse results than the full pipeline for tasks that were
misclassified as fast:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-3-routing
```

You can also disable routing without a full revert by defaulting `--path` to
`"deep"` in `run.py` and leaving the router code in place but unused — this
is a safe interim step if you want to keep investigating the classifier
without reverting the whole phase.

## Commit suggestion

```text
feat: add fast/normal/deep routing to reduce unnecessary model calls
```

## Done when

```text
Simple tasks can use a fast path that skips the Planner and the Critic/Fixer
loop, normal tasks use fewer calls than the full deep pipeline's default,
deep tasks still have access to the full pipeline, the selected path is
logged and recorded in run_summary.json, and both run.py and
orchestrator/graph.py implement the same routing behavior.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 3: routing, speed, and pipeline collapse.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- run.py
- orchestrator/graph.py
- orchestrator/config_loader.py
- config/models.yaml
- config/modes.yaml
- orchestrator/logger.py
- prompts/builder.txt

Implement the following:
1. Add a "paths" section to config/models.yaml defining fast/normal/deep
   path settings (skip_planner, skip_critic_fixer_loop, max_loops,
   threshold), and a get_path_settings() getter in orchestrator/config_loader.py.
2. Create orchestrator/router.py with classify_path(goal, mode, override)
   -> "fast"|"normal"|"deep" using deterministic heuristics (goal length,
   complexity keywords, mode), and get_path_config(path).
3. Wire path selection into run.py: add a --path CLI flag (auto/fast/normal/
   deep, default auto), call classify_path after the Supervisor step, skip
   the Planner call entirely when skip_planner is true, skip the Critic/
   Fixer loop entirely when skip_critic_fixer_loop is true (single Judge
   check on the Builder draft instead), and log the selected path via a new
   logger method. Record the path in run_summary.json.
4. Mirror the same routing behavior in orchestrator/graph.py's graph
   structure (conditional edges that skip node_planner and the
   critic/fixer/judge loop for the fast path).
5. Explicit CLI --max-loops/--threshold flags must still override the
   path's defaults when the user passes them.

Do not change which models are used per role — that is a separate phase.
Do not modify any file outside this scope.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_router.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Any remaining risks or TODOs
4. A suggested commit message
```
