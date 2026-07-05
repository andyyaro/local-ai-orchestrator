# Phase 12c Maintainer Report — Split Smoke Test and Strict Acceptance Test

## Goal

`scripts/local_acceptance.sh` mixed two different jobs: a lightweight
smoke test (does the pipeline run end-to-end?) and a strict quality
acceptance test (can a model satisfy a precise output constraint?). After
Phase 12b's fix, a human release check found the script still failed on a
50-word task with `llama3.2:3b` — but this is no longer a silent-pass bug:
the system correctly detects the constraint violation, attempts repair,
and fails safely. The problem is that requiring a tiny model to satisfy a
strict word count in a *smoke* test conflates "the pipeline is broken"
with "this particular model can't hit an exact number," which are very
different signals for a release check.

## What was changed

1. **`scripts/local_acceptance.sh` (smoke test, rewritten)** — still runs
   the same `llama3.2:3b` pipeline end-to-end and checks that
   `run_summary.json`/`final_output.txt` are produced, but no longer
   requires the final output to actually satisfy the 50-word constraint.
   Instead it keeps the genuinely useful part of the old check — the
   Phase 6b silent-pass regression guard — reframed as: *if* the real
   validator says the constraint was violated, `run_summary.json` must
   also report `passed: false` (never silently claim success). A small
   model correctly detecting and reporting its own constraint violation
   is a **pass** for this script now, not a failure.
2. **`scripts/strict_acceptance.sh` (new)** — the real quality gate.
   Uses `llama3.1:8b` (a stronger local model than the smoke test's
   `llama3.2:3b`), runs the same 50-word goal, and genuinely fails
   (`exit 1`) if the final output violates the constraint, printing the
   real validator's detail, the run's self-reported `passed` value, and
   `stop_reason` so the failure reason is unambiguous. It never pulls a
   model automatically: if `llama3.1:8b` isn't present in `ollama list`,
   it prints the exact `ollama pull llama3.1:8b` command and exits with a
   distinct skip code (`2`) rather than silently downloading or silently
   passing.
3. **`README.md`** — added a "Release Gates" section spelling out four
   distinct checks and when each applies: Unit/CI gate (ruff + pytest,
   required on every PR), Quick release check (adds
   `local_acceptance.sh`, required before tagging), Full
   release-candidate check (`eval.run_eval_suite`, slow, run after major
   pipeline/model changes rather than before every tag), and Strict local
   quality check (`strict_acceptance.sh`, optional/recommended for this
   immediate v2.0 tag).
4. **`docs/model-profiles.md`** — replaced the stale "Manual smoke test"
   section (which described a check that no longer matches the script's
   actual behavior) with an "Manual acceptance scripts" section describing
   both scripts and their distinct purposes, pointing to README.md as the
   canonical source for the full release-gate picture.

## Release-gate behavior changed

Before: `scripts/local_acceptance.sh` was both the smoke test and the
only quality gate, and it hard-failed on a tiny model's inability to hit
an exact word count — a genuine model-capability limitation, not a
pipeline defect.

After: the smoke test only verifies the pipeline runs end-to-end (or
fails safely) and never lies about pass/fail status. The strict quality
gate is a separate, explicitly optional script that uses a stronger model
and is allowed to fail loudly and slowly — and does not gate CI, PR merge,
or (per this phase's explicit instructions) this immediate v2.0 tag.

## Tests run

```
python -m ruff check .        → All checks passed!
python -m pytest tests/ -v    → 227 passed
```

No new Python code was added (both scripts are bash), so no new unit
tests were needed; existing test coverage (`test_validators.py`,
`test_model_config.py`, etc.) is unaffected and unchanged.

## Smoke test result

`bash scripts/local_acceptance.sh` — **passed** (exit 0), after one
transient retry:

- First attempt failed with a real Ollama timeout on `llama3.2:3b` itself
  during the Fixer step (`FatalModelError`, `run.py` exits 1) — an
  environment/memory-pressure issue from several large models (from
  earlier in this session) still resident, not caused by this phase's
  changes.
- After confirming only `llama3.2:3b` was loaded (`ollama ps`), the retry
  completed: the pipeline correctly reported `passed: false` and
  `stop_reason: hard_fail: ['dangerous_content', 'constraint_violation']`
  for the 50-word goal, and the new regression-guard check confirmed no
  silent-pass regression — exactly the intended outcome. `dangerous_content`
  appearing here is the Judge's own heuristic on prose about health
  topics (sleep deprivation, disease) and is unrelated to this phase's
  scope; the smoke test does not gate on it.

## Strict acceptance result

`bash scripts/strict_acceptance.sh` — ran (required model `llama3.1:8b`
was already available locally, confirmed via `ollama list`) and
**genuinely failed** (exit 1): even `llama3.1:8b`, across all three
repair loops and the Synthesizer's own attempt, produced outputs of
151–356 words against a 50-word target with a 20-word tolerance (30–70
acceptable). The script correctly printed the real validator's detail,
`run_summary.passed: False`, `stop_reason`, and a clear failure message
explaining this is a genuine quality-gate failure. Per this phase's
explicit scope, this is **documented as a known risk, not fixed** —
fixing exact-word-count adherence would mean changing prompting or
pipeline behavior, which is out of Phase 12c's scope (splitting release
gates only).

## Confirmation: full eval suite was not rerun

`python -m eval.run_eval_suite` was **not** run in this phase, per
explicit instruction. It already passed after Phase 12b (10 passed, 0
failed, 1 skipped, including `eval_simple_coding_task`), and Phase 12c
only restructures release-gate scripts/docs — it does not touch pipeline,
agent, or validator behavior, so there is nothing in this phase's diff
that the eval suite would newly exercise.

## Files changed

- `README.md`
- `docs/model-profiles.md`
- `scripts/local_acceptance.sh`
- `scripts/strict_acceptance.sh` (new)
- `docs/audits/2026-07-04-phase-12c-maintainer-report.md` (new)

## Remaining risks

- **Exact word-count constraints are hard for local models in general** —
  confirmed now with both a small (`llama3.2:3b`) and a stronger
  (`llama3.1:8b`) model failing the same 50-word target by a wide margin.
  This is a pre-existing limitation of instruction-following at this
  model scale, not something this phase introduces or is scoped to fix.
  A future phase could explore prompt changes (e.g. explicit word-count
  self-checking in the Builder/Fixer prompts) or a programmatic
  truncation/expansion repair step, but that is new pipeline behavior,
  correctly out of scope here.
- `strict_acceptance.sh`'s `STRICT_MODEL` is hardcoded to `llama3.1:8b`;
  if that model is ever removed from `config/models.yaml`'s profiles, the
  script's model choice would need to be revisited (it doesn't read
  `active_profile` — it deliberately picks a fixed, known-stronger model
  rather than whatever profile happens to be active).
- Neither acceptance script is wired into CI (unchanged from before this
  phase) — both require local Ollama with the relevant model already
  pulled, and are meant to be run by a human before a release, not by an
  automated pipeline.

## Whether v2.0 is ready for human tag approval

**Yes, from this phase's perspective.** All four release gates now have a
clear, honest purpose: CI gate (ruff + pytest) passes, smoke test passes,
the full eval suite already passed after Phase 12b, and the strict
quality gate — explicitly optional for this tag — ran and surfaced a real,
now-documented model-capability limitation rather than a pipeline defect.
Tagging v2.0 is a human decision; this phase does not tag a release or
create a GitHub Release, per instructions.

## Commit

```
chore: split smoke and strict acceptance gates
```
