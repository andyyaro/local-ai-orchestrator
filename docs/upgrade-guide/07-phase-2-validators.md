# 07 — Phase 2: Deterministic Validators

## Goal

Fix the 120-word constraint failure permanently by adding deterministic,
code-level constraint checks that run before (and override) the Judge's
score — the same way `orchestrator/code_runner.py` already overrides the
Judge for broken code.

## Why it matters

The smoke test that ignored a 120-word limit did so because nothing in the
codebase checks word count. The Judge is an LLM (`agents/judge.py`, scored
against the rubric in `prompts/judge.txt`), and LLM judges are well-documented
to be unreliable at exactly this kind of precise, countable constraint —
counting words is a deterministic operation, not a judgment call, and
deterministic operations belong in Python, not in a model's context window.

A validator is a Python check that enforces a rule before the LLM Judge gets
involved. For example, if the user asks for exactly 120 words, the validator
counts the words. The Judge should not be trusted to notice this reliably
because word count is deterministic and should be checked by code.

This repo already has exactly this pattern working for code correctness:
`orchestrator/code_runner.py`'s `verify_draft_code()` runs the code for real,
and `run.py`'s `_apply_code_verification_to_verdict()` forces the Judge's
verdict to fail (`pass = False`, `total_score = 0`, hard fail `broken_code`)
regardless of what score the Judge gave. Phase 2 adds the same mechanism for
constraint violations instead of code failures — a new `constraint_violation`
hard fail that the Judge cannot override with a high score.

## Files likely touched

```text
orchestrator/validators.py   (new)
tests/test_validators.py     (new)
run.py                        (wire in validator results, mirroring code verification)
orchestrator/graph.py         (same wiring, LangGraph pipeline)
```

Files to inspect first (read-only):

```text
run.py
orchestrator/graph.py
orchestrator/code_runner.py
agents/judge.py
prompts/judge.txt
config/modes.yaml
tests/test_judge.py
tests/test_code_runner.py
```

Recall from `00-overview.md` that `run.py` and `orchestrator/graph.py` are two
parallel pipeline implementations — this phase must wire validator
enforcement into both, or explicitly document why one was skipped.

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-2-validators
```

2. Create `orchestrator/validators.py`. This module has no dependency on any
   agent, model, or network call — it operates purely on the goal string and
   the draft string. Design it around these functions:

   - `extract_word_limit(goal: str) -> tuple[int | None, str | None]`
     Parses the raw goal text for a word-count constraint and returns
     `(limit, mode)` where `mode` is one of `"exact"`, `"max"`, or `"min"`,
     or `(None, None)` if no constraint is found. This must be a plain regex
     search — no model call. Cover phrasings like "120 words", "in exactly
     120 words", "no more than 500 words", "at least 50 words", "300-word".

   - `count_words(text: str) -> int`
     Splits on whitespace and counts tokens. Keep this simple and
     predictable — don't try to be clever about hyphenated words or
     contractions; document the one rule you pick (e.g. "split on
     whitespace") so it's auditable.

   - `check_word_limit(draft: str, limit: int, mode: str, tolerance: int = 0) -> ValidationResult`
     Compares `count_words(draft)` against `limit` according to `mode`.
     Consider a small tolerance (for example, ±5%) for `"exact"` mode so a
     121-word draft against a 120-word goal isn't punished as harshly as a
     300-word draft — but document the tolerance value and why you picked
     it, since "close enough" is a judgment call you're making once, in
     code, rather than leaving to chance every run.

   - `check_required_sections(draft: str, required: list[str]) -> ValidationResult`
     Checks that each required heading or keyword appears in the draft
     (case-insensitive substring or heading match).

   - `check_forbidden_phrases(draft: str, forbidden: list[str]) -> ValidationResult`
     Checks that none of the forbidden phrases appear in the draft.

   - `check_bullet_count(draft: str, min_bullets: int | None, max_bullets: int | None) -> ValidationResult`
     Counts lines starting with `-`, `*`, or a numbered list marker.

   - `check_json_schema(draft: str, required_keys: list[str]) -> ValidationResult`
     Attempts to parse the draft as JSON and confirms required top-level
     keys are present. Reuse the same forgiving-parse approach
     `agents/judge.py`'s `_parse_json()` already uses (strip code fences,
     find first `{`/last `}`) rather than inventing a second JSON-extraction
     strategy in the same codebase.

   - `check_code_block_presence(draft: str, required: bool) -> ValidationResult`
     For coding-mode tasks, confirms at least one fenced code block exists
     (or, for tasks that should *not* contain code, that none does).

   - A shared `ValidationResult` shape — either a small dataclass or a plain
     dict — with at minimum: `rule` (str, e.g. `"word_limit"`), `passed`
     (bool), `detail` (str, human-readable explanation for logs and the
     rationale field).

   - `run_validators(goal: str, draft: str, mode: str) -> list[ValidationResult]`
     The single entry point `run.py` and `orchestrator/graph.py` call. It
     decides which checks are relevant (word limit is always checked if
     `extract_word_limit` finds one; code-block presence only applies in
     `mode == "coding"`; and so on) and returns the full list of results,
     not just the failures — so passing checks can be logged too if useful
     later.

3. Wire validator enforcement into `run.py`, in the same place and the same
   style as `_apply_code_verification_to_verdict()`. Add a new helper:

```python
def _apply_validator_results_to_verdict(verdict: dict, validator_results: list) -> dict:
    """Force a hard fail when a deterministic constraint check fails."""
    failed = [r for r in validator_results if not r.passed]
    if not failed:
        return verdict

    hard_fails = verdict.get("hard_fails", [])
    if not isinstance(hard_fails, list):
        hard_fails = []
    if "constraint_violation" not in hard_fails:
        hard_fails.append("constraint_violation")

    verdict["hard_fails"] = hard_fails
    verdict["pass"] = False
    verdict["total_score"] = min(verdict.get("total_score", 0), 0)
    detail = "; ".join(r.detail for r in failed)
    verdict["rationale"] = (
        str(verdict.get("rationale", ""))
        + f"\n\nDeterministic constraint check failed before Judge pass/fail "
        + f"was accepted: {detail}"
    ).strip()
    verdict["validator_failures"] = [r.rule for r in failed]
    print(f"  [Validators] Hard fail: constraint_violation overrides Judge score ({detail})")
    return verdict
```

   Call this right after the existing `_apply_code_verification_to_verdict`
   call inside the loop in `run_pipeline()`, passing
   `run_validators(refined_goal, revised, mode)`. Save the validator results
   to the run directory the same way code verification results are saved
   (for example `loop{iteration:02d}_validators.json`), so they're visible in
   `runs/<timestamp>/` alongside the other loop artifacts.

4. Mirror the same wiring in `orchestrator/graph.py`'s `node_judge()` —
   this pipeline currently has no code-verification-style override at all
   (only `run.py` has it), so adding validators here is a good moment to
   also confirm whether the LangGraph path already needs the same
   code-verification parity fix as a separate, explicitly-scoped follow-up
   (do not silently fix that as part of this phase — note it and ask).

5. Do not modify `prompts/judge.txt`'s rubric to try to make the Judge
   "better at counting." The point of this phase is that the Judge is no
   longer the thing responsible for constraint enforcement at all.

## Tests to add

Create `tests/test_validators.py` covering at minimum:

- `extract_word_limit` correctly parses "120 words", "in exactly 120 words",
  "no more than 500 words", "at least 50 words", and returns `(None, None)`
  for a goal with no word constraint.
- `count_words` returns the expected count for a known string.
- `check_word_limit` fails a draft that is far outside the limit, and passes
  one that is within tolerance.
- `check_required_sections`, `check_forbidden_phrases`, `check_bullet_count`,
  `check_json_schema`, and `check_code_block_presence` each have at least one
  passing and one failing case.
- `run_validators` returns an empty-failures list for a mode with no
  applicable constraints, and returns the expected failing rule name for a
  draft that violates a detected word limit.
- A regression test that reproduces the original bug directly: a goal
  containing "in exactly 120 words" and a draft of, say, 300 words, must
  produce a failing `ValidationResult` for `"word_limit"`.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_validators.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_validators.py` passes, including the 120-word regression case.
- The full `tests/` suite still passes (existing Judge/database/code-runner
  tests are unaffected).
- Manually running the pipeline with a word-limited goal and an
  intentionally-too-long draft shows `[Validators] Hard fail:
  constraint_violation overrides Judge score` in the terminal output, and
  `run_summary.json` / the loop's judge JSON shows `"constraint_violation"`
  in `hard_fails`.

## If it fails

- A real, well-formed 120-word draft is being flagged as failing: check your
  tolerance value in `check_word_limit` — a tolerance of 0 is too strict for
  natural language generation; re-read the tolerance rule you documented in
  step 2 and adjust it deliberately, don't just widen it until the test
  passes without understanding why.
- `extract_word_limit` misses a real phrasing from an actual goal you tried:
  add that phrasing as a new regression test case first, then fix the regex
  — don't fix the regex by guessing without a failing test pinning down the
  exact input.
- The full `tests/` suite breaks after wiring the new hard-fail logic into
  `run.py`: check whether `_should_break_on_hard_fail()` (which already has
  special-cased handling for `broken_code` in coding mode) needs the same
  kind of consideration for `constraint_violation`, or whether it should
  simply stop the loop immediately like other hard fails.

## Rollback plan

If validator enforcement causes more harm than good (for example, false
positives blocking otherwise-good runs), revert just this phase's commits:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged, remove the branch:

```bash
git checkout main
git branch -D phase-2-validators
```

⚠️ Do not disable validator enforcement by weakening `_apply_validator_results_to_verdict`'s
threshold in place without a corresponding test — if it's not working the
way you want, that's a signal to fix the specific validator rule, not to make
enforcement quietly optional.

## Commit suggestion

```text
feat: add deterministic constraint validators
```

## Done when

```text
A 120-word constrained task cannot pass unless it satisfies the word-count
validator, tests/test_validators.py passes including the regression case,
and the full test suite still passes with no unrelated files changed.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 2: deterministic validators.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- run.py
- orchestrator/graph.py
- orchestrator/code_runner.py
- agents/judge.py
- prompts/judge.txt
- config/modes.yaml
- tests/test_judge.py
- tests/test_code_runner.py

Implement the following:
1. Create orchestrator/validators.py with pure-Python, non-LLM constraint
   checks: extract_word_limit, count_words, check_word_limit,
   check_required_sections, check_forbidden_phrases, check_bullet_count,
   check_json_schema, check_code_block_presence, a shared ValidationResult
   shape, and a run_validators(goal, draft, mode) entry point.
2. Wire a new _apply_validator_results_to_verdict() helper into run.py,
   following the exact same pattern as the existing
   _apply_code_verification_to_verdict() function: force pass=False,
   total_score=0, and add a "constraint_violation" hard fail when any
   validator fails. Save validator results per loop iteration to the run
   directory the same way code verification results are saved.
3. Apply the same wiring to orchestrator/graph.py's node_judge(). If that
   pipeline is missing the equivalent code-verification override entirely,
   do not silently add it as part of this phase — stop and report it as a
   separate, out-of-scope finding instead.
4. Do not modify prompts/judge.txt's rubric.

Create tests/test_validators.py covering extract_word_limit for multiple
phrasings, count_words, each check_* function's pass and fail cases, and a
direct regression test reproducing the original bug: a goal saying "in
exactly 120 words" with a 300-word draft must fail the word_limit check.

Do not modify any file outside this scope.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_validators.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Any remaining risks or TODOs (including whether orchestrator/graph.py
   needed the code-verification-parity fix noted above)
4. A suggested commit message
```
