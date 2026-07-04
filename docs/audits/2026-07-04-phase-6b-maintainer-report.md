# Phase 6b Maintainer Report — Constraint Preservation and Memory Closure

## Bug being fixed

A local acceptance run (`runs/20260704_171324/`) exposed a critical behavior
bug: the command `Write a 50-word summary of why sleep matters.` produced a
~450-word essay with citations, yet the run reported `score 88/100,
passed: true`, and `local_acceptance.sh` reported success.

Root cause, confirmed by inspecting the run artifacts:

- `00_supervisor.json`'s `refined_goal` completely dropped the "50-word"
  constraint, rewriting it into an open-ended prompt ("Explain the
  physiological and psychological importance of sleep in humans...").
- `run.py` and `orchestrator/graph.py` both called
  `run_validators(refined_goal, draft, mode)` — validating only against the
  Supervisor's paraphrase, never the user's original text. Since
  `refined_goal` no longer contained a word-count pattern,
  `extract_word_limit()` found nothing, `loop01_validators.json` came back
  `[]`, and no `constraint_violation` hard fail was ever raised.
- `scripts/local_acceptance.sh` only checked that `run_summary.json` and
  `final_output.txt` existed — it had no awareness of the goal's content at
  all, so it could never have caught this regardless of the validators bug.
- Separately, `agents/synthesizer.py`'s prompt is labeled "ORIGINAL GOAL"
  but was being fed `refined_goal`, not the true original text, in both
  `run.py` and `orchestrator/graph.py` — and nothing validated the
  Synthesizer's output at all, so even a correctly-validated draft could be
  silently expanded into an invalid final answer at the very last step.

## A. Constraint preservation — what changed

1. **`orchestrator/validators.py`** — `run_validators()` gained an optional
   keyword-only `original_goal` parameter. When given, word-limit
   extraction runs against `original_goal` (the user's literal text)
   instead of `goal` (which may be a Supervisor paraphrase that dropped the
   constraint). Omitting it preserves the exact prior behavior, so all
   existing direct callers/tests of `run_validators(goal=..., draft=...,
   mode=...)` are unaffected.
2. **`run.py`** and **`orchestrator/graph.py`** — both `run_validators()`
   call sites (fast-path and loop-path in `run.py`; `node_judge()` in
   `graph.py`) now pass `original_goal=goal` / `original_goal=state["goal"]`,
   so the user's literal constraint is always checked, regardless of what
   the Supervisor rewrote it into.
3. **Synthesizer now receives the true original goal.** `run.py`'s and
   `graph.py`'s Synthesizer calls changed from `goal=refined_goal` to
   `goal=goal` / `goal=state["goal"]`, so the prompt's "ORIGINAL GOAL" label
   is now accurate and the model actually sees the literal constraint text
   (e.g. "50-word summary") rather than a paraphrase that may have dropped it.
4. **Post-synthesis guard.** After the Synthesizer runs, both `run.py` and
   `graph.py` now call `run_validators(goal, final_output, mode)` against
   the true original goal and save the result (`final_validators.json`). If
   the Synthesizer's output fails, it is discarded and replaced with the
   pre-synthesis `best_draft` (which already passed constraint validation
   in the loop), and `metrics.record_hard_fail("synthesizer_constraint_violation")`
   is recorded. This directly satisfies "the Synthesizer cannot expand a
   valid draft into an invalid final answer" — a bad Synthesizer output can
   never reach the user unchecked.
5. **Prompt reinforcement (defense in depth).** `prompts/supervisor.txt` now
   explicitly instructs the Supervisor to preserve every hard constraint
   (word counts, required sections, forbidden content, output format)
   verbatim in its refined goal — dropping one while "clarifying" the goal
   is now explicitly called out as a failure mode. `prompts/synthesizer.txt`
   now explicitly states the draft has already been validated against the
   original goal's constraints and polishing must never violate them. These
   prompt changes are a secondary defense; the actual enforcement is the
   code-level fix above (LLMs are not reliably instructable — see
   "Verification" below).

## B. Local acceptance strengthening — what changed

`scripts/local_acceptance.sh` now runs a real content check after
confirming the artifact files exist: it imports
`orchestrator.validators.check_word_limit` directly (not a duplicated bash
word-count regex) and checks `final_output.txt` against the 50-word target
with a 20-word tolerance, printing the check detail and exiting non-zero if
it fails. This reuses the same tolerance logic the real pipeline enforces,
so the smoke test stays in sync with `orchestrator/validators.py` rather
than drifting into its own duplicated rule.

Regression test: `tests/test_pipeline_routing.py::test_pipeline_fails_when_supervisor_drops_original_word_limit`
reproduces the exact original bug end to end (mocked Supervisor drops the
constraint, mocked Builder returns a 300-word draft, mocked Judge scores it
100/pass) and asserts the run now reports `passed: False`,
`final_score: 0`, and `constraint_violation` in both `stop_reason` and
`metrics.hard_fails`. Verified this test fails against the pre-fix code
(see "Verification" below) and passes against the fix.

A second regression test,
`test_pipeline_reverts_final_output_when_synthesizer_violates_constraint`,
covers the Synthesizer-guard case: a compliant `best_draft` (20 words
against a 20-word-exact goal) paired with a mocked Synthesizer that returns
a 300-word expansion. Asserts `final_output` — both the return value and
`final_output.txt` on disk — is reverted to the compliant `best_draft`, and
`metrics.hard_fails["synthesizer_constraint_violation"] == 1`.

## C. Memory-discipline gap closure

### C1 — `mode_overrides` + `active_profile` mixing

Added `orchestrator.config_loader.get_effective_role_models(mode,
profile_name=None)`: computes the full role→model mapping for a
profile+mode combination, then checks whether the merged result
(profile defaults + `mode_overrides`) references more than one distinct
14B-class model name. If so, every role holding a 14B-class model is
brought in line with the override's model (the override is trusted as the
more task-relevant choice — e.g. a coder model for a coding-classified
goal) rather than leaving roles split across two different resident
families. `get_model_for_role()` now delegates to this function instead of
applying `mode_overrides` per-role independently.

Concretely: `active_profile: serious` + a goal classified `mode="coding"`
previously produced `builder`/`fixer` on `qwen2.5-coder:14b` while
`judge`/`synthesizer` stayed on `serious`'s `qwen2.5:14b` — two resident
14B-class families in one run. Now all four heavy roles resolve to
`qwen2.5-coder:14b` for that combination. Verified with
`tests/test_model_config.py::test_effective_role_models_for_serious_profile_with_coding_mode_uses_one_14b_family`
and its sibling tests (`debugging` mode; `low_memory` profile, where the
single-14B override is correctly left alone since it doesn't create a
second family).

### C2 — wiring `get_num_ctx_for_profile()` into runtime calls

`get_num_ctx_for_profile()` existed since Phase 6 but was never called
outside its own tests. `run.py`'s `run_pipeline()` now computes
`run_num_ctx = get_num_ctx_for_profile()` once per run and passes
`num_ctx=run_num_ctx` into every agent constructor (Supervisor, Planner,
Builder, Critic, Fixer, Judge, Synthesizer) — the same pattern Phase 5b
used to wire `metrics` through. `orchestrator/graph.py` gained a
`_num_ctx()` helper mirroring `_role_model()`, called the same way in every
node. `agents/base_agent.py` already accepted a `num_ctx` constructor
parameter (added in an earlier phase) and already threads it into
`call_with_resilience()` — no agent-layer changes were needed, only the
call-site wiring in `run.py`/`graph.py`.

## Files changed

- `orchestrator/validators.py`
- `orchestrator/config_loader.py`
- `orchestrator/graph.py`
- `run.py`
- `prompts/supervisor.txt`
- `prompts/synthesizer.txt`
- `scripts/local_acceptance.sh`
- `tests/test_validators.py`
- `tests/test_model_config.py`
- `tests/test_pipeline_routing.py`
- `docs/audits/2026-07-04-phase-6b-maintainer-report.md` (new)

## Tests run

```
ruff check .                       → All checks passed!
pytest tests/test_validators.py -v    → 35 passed
pytest tests/test_model_config.py -v  → 12 passed
pytest tests/ -v                   → 102 passed
```

Verified both new pipeline-level regression tests fail against the
pre-fix `run.py`/`orchestrator/validators.py` (stashed those two files and
re-ran): both failed as expected, confirming they catch the real bug and
aren't just descriptive.

## Local acceptance result

`./scripts/local_acceptance.sh` was run twice against the real local
Ollama instance with `llama3.2:3b` (already pulled, no downloads). Both
runs: the pipeline completed end to end, but the Builder's first draft
came in at 265 and 237 words respectively against the 50-word target —
`llama3.2:3b` does not reliably follow precise word-count instructions
even with the strengthened Supervisor prompt (which correctly preserved
"within a 50-word limit" in its refined goal both times — the model simply
did not comply with its own instruction). The validators correctly
hard-failed both runs (`score 0`, `passed: False`,
`hard_fail: ['constraint_violation']`), and the acceptance script's new
word-count check correctly caught the violation and exited non-zero both
times, printing e.g. `word count 265 is outside the 20-word tolerance for
exact target 50`.

**This is the fix working correctly, not a regression.** The whole point
of Part B was that the smoke test must no longer silently succeed
regardless of content — it now doesn't. The remaining variable is
`llama3.2:3b`'s own instruction-following reliability for precise word
counts on a single fast-path pass, which is a pre-existing model-capability
limitation, not something introduced by or fixable within this phase's
"smallest safe changes" scope. Using a stronger model, or a mode/path that
allows Critic/Fixer iteration, would likely converge on compliance — but
note the related discovery below.

**Related discovery (not fixed in this phase):** the pipeline's existing
`_should_break_on_hard_fail()` in `run.py` (and the equivalent inline logic
in `orchestrator/graph.py`'s `node_judge`) stops the Critic/Fixer loop
immediately on *any* hard fail in non-coding modes, with no iterative
retry — unlike `broken_code` in coding mode, which is deliberately allowed
to continue until `max_loops` so the Fixer can use execution feedback.
Manually testing `--path normal --max-loops 3` against the same goal
confirmed the loop still stopped after iteration 1 on the
`constraint_violation` hard fail, never giving the Critic/Fixer a chance
to shrink the draft toward the word target. Extending hard-fail retry
behavior to `constraint_violation` (mirroring the `coding`/`broken_code`
carve-out) would likely make real runs against small models converge more
often, but changing loop-continuation semantics beyond constraint
*detection* was not part of this phase's explicit scope and is flagged
here as a candidate follow-up rather than silently added.

## PR / CI / merge

See below (filled in after PR creation, CI, and merge).

## Remaining risks

- `llama3.2:3b`'s unreliable word-count compliance on the fast path (see
  above) — a model-capability limitation, not a code defect, but worth
  knowing before treating `local_acceptance.sh`'s pass/fail as a strict
  gate for every local model.
- The hard-fail-stops-the-loop-immediately behavior for non-coding
  `constraint_violation` (see above) means a single bad Builder draft on
  the fast path has no chance for the pipeline to self-correct within one
  run — flagged as a follow-up, not fixed here.

## v1.1 / Phase 7 readiness

Both Phase 6 gaps named in this phase's scope are closed:
`mode_overrides` + `active_profile` can no longer mix multiple 14B-class
families in one run, and `get_num_ctx_for_profile()` is now wired into the
real per-call `num_ctx` used by every agent. Combined with the
constraint-preservation fix, nothing found in this phase blocks Phase 7.
Phase 7 was not started.

## Commit

```
fix: preserve user constraints through final output
```
