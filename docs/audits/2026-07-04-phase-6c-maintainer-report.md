# Phase 6c Maintainer Report — Non-Coding Constraint Repair Loop

## Gap being closed

Phase 6b made validators check the original user goal and guarded the
Synthesizer's final output, but it also surfaced (and deliberately left
open, as a flagged follow-up) a real gap: any non-coding `constraint_violation`
hard fail stopped the pipeline immediately — `_should_break_on_hard_fail()`
only allowed iterative retries for `broken_code` in coding mode. A writing
task that missed a word-count target got exactly one shot; if the Builder's
first draft (or the fast path's single pass) violated the constraint, the
run failed on the spot, even though a Critic/Fixer pass might easily have
fixed it (e.g. "cut this to 50 words"). Separately, the fast path skips
Critic/Fixer entirely by design, so even in the normal/deep paths a
constraint violation had no realistic repair route without an explicit
carve-out.

## Repair-loop behavior changed

1. **`orchestrator/validators.py`** — `_should_break_on_hard_fail` moved
   here (public, renamed `should_break_on_hard_fail`) so `run.py` and
   `orchestrator/graph.py` share one implementation instead of duplicating
   it. Added a new carve-out: if `hard_fails` is *exactly*
   `{"constraint_violation"}` and `iteration < max_loops`, the loop
   continues instead of stopping — in **any** mode, not just coding. If
   any other, unrecognized hard fail is present alongside it (e.g. a
   Judge-reported `dangerous_content` or `judge_parse_error`), it still
   stops immediately, exactly as before: a constraint violation can delay
   failure for a repair attempt, but it can never be silently dropped
   alongside a failure mode the system doesn't know how to repair. The
   pre-existing coding-mode `broken_code` carve-out is **untouched** — the
   original condition line is preserved verbatim, and new tests
   (`tests/test_validators.py`) prove it's unaffected by anything added in
   this phase.
2. **`run.py`** — extracted the Critic→Fixer→(code verify)→validate→Judge
   sequence into a shared helper, `_run_critic_fixer_judge_iteration()`,
   used by both the normal/deep loop (unchanged behavior, now just calling
   the helper) and a new fast-path repair fallback. The fast path's first
   pass behaves exactly as before (no Critic/Fixer, single validate+judge
   call); if that pass hard-fails on a repairable `constraint_violation`
   *and* `effective_max_loops > 1`, it now falls back into the same
   Critic/Fixer/Judge cycle for the remaining allowed iterations instead of
   failing immediately. Critic/Fixer agent objects are now constructed
   unconditionally (before the fast/normal branch split) — cheap, since
   construction doesn't call the model — so the fast path can reach for
   them without a separate code path.
3. **Actionable feedback threading** — each iteration's failed-validator
   detail text (e.g. `"word count 265 is outside the 5-word tolerance for
   exact target 50"`) is now threaded into the *next* iteration's critique
   as a `"DETERMINISTIC CONSTRAINT FEEDBACK FROM PREVIOUS REVISION"`
   section, mirroring the existing `previous_code_feedback` pattern used
   for coding-mode execution errors. This gives the Fixer something
   concrete to act on instead of re-discovering the same violation.
4. **Revalidation against the original goal** — unchanged from Phase 6b:
   `_run_critic_fixer_judge_iteration()` calls
   `run_validators(refined_goal, revised, mode, original_goal=goal)` every
   iteration, so a repaired draft is checked against the user's literal
   constraint, not a paraphrase.
5. **`orchestrator/graph.py`** — mirrored the same repair behavior for the
   LangGraph pipeline. Since `graph.py`'s Critic→Fixer→Judge cycle is
   already a graph loop (not a Python `for` loop), the fix is smaller here:
   `node_judge()` only force-stops on the fast path's very first pass
   (`fast_first_pass = skip_critic_fixer_loop and iteration == 1`); if that
   first pass hard-fails on a repairable violation, `should_continue=True`
   is returned and `route_after_judge()` (no longer unconditionally forcing
   `"synthesizer"` for `skip_critic_fixer_loop`) routes back to
   `"critic"` — reusing the existing graph edges with no new nodes needed.
   `node_critic()` now threads `previous_validator_feedback` from state
   into its critique the same way. `orchestrator/state.py` gained the
   corresponding `previous_validator_feedback` field.
6. **`prompts/fixer.txt`** — added an explicit exception to the existing
   "do not shorten the draft" and "must be at least as long as the
   original" rules: when the critique includes a `"DETERMINISTIC
   CONSTRAINT FEEDBACK"` section, satisfying that constraint (even by
   cutting content) overrides those rules. Without this, the Fixer's own
   prompt directly contradicted the repair this phase depends on.
7. **`scripts/local_acceptance.sh`** — bumped `--max-loops` from `1` to
   `3`. With `max_loops=1`, `should_break_on_hard_fail`'s `iteration <
   max_loops` check is never true, so the repair carve-out can never
   trigger — the smoke test needs room for at least one repair attempt to
   actually exercise the new behavior.

## Coding-mode protection (requirement 5)

`should_break_on_hard_fail`'s original `mode == "coding" and "broken_code"
in hard_fails and iteration < max_loops` line is unchanged, character for
character. New tests explicitly cover: `broken_code` alone in coding mode
continues (unchanged); `broken_code` alongside `constraint_violation` in
coding mode still continues (both repairable together — this combination
already existed before this phase, since `_apply_code_verification_to_verdict`
and `apply_validator_results_to_verdict` can both fire on the same
iteration); `broken_code` reaching `max_loops` still stops; `broken_code`
outside coding mode still stops immediately (the carve-out is
coding-mode-only, unchanged).

## Files changed

- `orchestrator/validators.py` — `should_break_on_hard_fail` added (moved
  from `run.py`, made public, extended with the `constraint_violation`
  carve-out)
- `run.py` — shared `_run_critic_fixer_judge_iteration()` helper; fast-path
  repair fallback; validator-feedback threading; imports
  `should_break_on_hard_fail` from `orchestrator.validators`
- `orchestrator/graph.py` — `node_judge`/`node_critic`/`route_after_judge`
  updated to mirror the repair behavior using the same shared function
- `orchestrator/state.py` — added `previous_validator_feedback` field
- `prompts/fixer.txt` — exception to the "don't shorten" rules for
  constraint-driven repairs
- `scripts/local_acceptance.sh` — `--max-loops` bumped to `3`
- `tests/test_validators.py` — 9 new tests for `should_break_on_hard_fail`
  (repair carve-out behavior, coding-mode protection)
- `tests/test_pipeline_routing.py` — 3 new end-to-end tests: successful
  repair via Critic/Fixer, clear failure after exhausting repair attempts,
  and no-repair-when-no-room-in-config (regression guard for the
  `max_loops=1` default)
- `docs/audits/2026-07-04-phase-6c-maintainer-report.md` (new)

## Tests run

```
ruff check .                          → All checks passed!
pytest tests/test_validators.py -v    → 43 passed
pytest tests/test_pipeline_routing.py -v → 8 passed
pytest tests/ -v                      → 113 passed
```

Verified both new end-to-end repair tests
(`test_fast_path_repairs_constraint_violation_via_critic_fixer` and
`test_fast_path_repair_fails_clearly_when_still_violating_after_max_loops`)
fail against the pre-6c code (stashed the run.py/graph.py/validators.py/
state.py/fixer.txt changes and re-ran): both failed as expected — the
pre-fix pipeline hard-fails on iteration 1 with no repair attempt in
either case — confirming the tests catch the real gap, not just describe
it.

## Local acceptance result

`./scripts/local_acceptance.sh` was run three times against the real local
Ollama instance (`llama3.2:3b`, already pulled, no downloads):

- **Run 1**: the Judge returned malformed JSON (a pre-existing, unrelated
  flakiness in `llama3.2:3b`'s output), producing `hard_fails:
  ["judge_parse_error", "constraint_violation"]`. Since this is *not*
  exactly `{"constraint_violation"}`, repair correctly declined to trigger
  (by design) and the run failed immediately, same as before.
- **Run 2**: the Judge hallucinated a `"dangerous_content"` hard fail on
  entirely benign text, again combining with `constraint_violation` — same
  conservative non-trigger, same immediate failure.
- **Run 3**: `hard_fails == ["constraint_violation"]` alone on the first
  pass — the repair path triggered exactly as designed: `[Repair] Fast
  path validator failure is repairable -- falling back to Critic/Fixer for
  remaining iterations` printed, and two full Critic→Fixer→Judge repair
  iterations ran (loop 2 and loop 3), each with the
  `DETERMINISTIC CONSTRAINT FEEDBACK` section correctly threaded into the
  critique. `llama3.2:3b`'s Fixer still could not get under 50 words after
  two genuine repair attempts (362 and 214 words), so the run correctly
  and clearly failed at the end (`passed: NO`, `final_score: 0`,
  `iterations_run: 3`), and the smoke test's word-count check correctly
  failed (`word count 266 is outside the 20-word tolerance for exact
  target 50`).

**This is the mechanism working exactly as specified, not a regression.**
Run 3 demonstrates all four "Expected behavior" bullets from the task
except the successful-repair case (a 250-word draft repairs down to
compliant), which `llama3.2:3b` was simply not capable enough to achieve
in two attempts — that exact case is proven deterministically by
`test_fast_path_repairs_constraint_violation_via_critic_fixer` (a mocked
Fixer that does produce a compliant 50-word draft on the first repair
attempt, and the run passes). The remaining variable across all three real
runs is `llama3.2:3b`'s own reliability (JSON parsing, hallucinated hard
fails, precise word-count instruction-following) — a model-capability
limitation carried over from Phase 6b's identical finding, not a defect
introduced by this phase.

## Remaining risks

- `llama3.2:3b`'s Judge output is not reliably valid JSON and occasionally
  hallucinates hard-fail reasons unrelated to the actual text (observed
  twice in three runs here). This pre-dates this phase and affects how
  often the repair path even gets a chance to run in practice with this
  specific small model — using a larger Judge model, or model-fast
  override, would likely reduce this.
- The repair loop does not implement the normal path's "stalled
  improvement" early-stop check — it will use all allowed iterations
  before giving up even if the score isn't improving. This is a
  deliberately conservative simplification (favors more repair attempts,
  never fewer) rather than a defect, but is worth knowing.
- Repair is only attempted when `constraint_violation` is the *sole* hard
  fail. This is intentional (never guess when an unknown failure mode is
  also present), but means a Judge that spuriously reports an unrelated
  hard fail (as seen in two of the three real runs above) prevents repair
  from being attempted even when the constraint violation itself would
  have been fixable.

## Phase 7 readiness

Yes — the repair loop is additive and defensive (it only ever delays a
failure for a bounded, config-limited number of extra iterations; it never
allows invalid output to pass). Nothing found in this phase blocks Phase 7.
Phase 7 was not started.

## Commit

```
fix: repair non-coding constraint violations before failing
```
