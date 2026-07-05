# Phase 12b Maintainer Report — Fix Coding Mode Classification

## Goal

Fix a release-blocking bug found by Phase 12's eval suite: the Supervisor
agent classified an unambiguous coding goal (e.g. "Write a Python function
called double(n) that returns n multiplied by 2. Include a pytest test...")
as `mode="general"` instead of `mode="coding"`, using the `serious`
profile's default supervisor model (`llama3.1:8b`). Verified directly
against raw `00_supervisor.json` output before this phase began.

## Root cause

The Supervisor's mode selection is entirely LLM-driven: it asks
`llama3.1:8b` to pick one word from a fixed list of modes based on the raw
goal text. There was no deterministic check preventing the model from
picking a wrong mode for an obviously-coding request. This is exactly the
same class of problem `orchestrator/router.py` already solves for
fast/normal/deep path classification — a model call is heuristic and can
be wrong, so a deterministic backstop is needed wherever a
misclassification would silently change pipeline behavior.

## What was built

1. **`orchestrator/mode_classifier.py` (new)** — `has_obvious_coding_signal(goal)`,
   a pure regex/word-boundary keyword matcher (no model call) against the
   phase's explicit signal list: code, function, class, script, bug,
   error, traceback, pytest, unit test(s), refactor, implement, write a
   program, Python, JavaScript, TypeScript, HTML, CSS, SQL, API, CLI,
   repository/repo, file edit(s). Mirrors `router.py`'s existing
   deterministic-classifier design. Word-boundary (`\b`) matching avoids
   substring false positives like `class` inside `classic` or `code`
   inside `codependent`.
2. **`agents/supervisor.py`** — after parsing the model's own
   `REFINED GOAL:`/`MODE:` response, added a guardrail: if the model
   picked a mode other than `coding` or `debugging`, and the **original
   raw goal** (not the model's own refined/rephrased goal) contains an
   obvious coding signal, the mode is force-overridden to `coding` and a
   `[Supervisor] Overriding mode ...` line is printed. Checked against the
   original goal deliberately — the model's own rephrasing is exactly
   what can drop the signal in the first place, mirroring the
   original-vs-refined-goal precedent already established for hard
   constraint preservation (Phase 6b). The override never fires when the
   model already picked `coding` or `debugging`, so it cannot conflict
   with a correct debugging classification.
3. **`prompts/supervisor.txt`** — added a `CRITICAL` bullet under "HOW TO
   REWRITE THE GOAL" instructing the model itself that any goal asking
   for actual code, a function, a class, a script, a bug fix, or tests
   must be classified `coding`/`debugging`, never `general`/`writing` —
   defense-in-depth alongside the code-level guardrail, not a replacement
   for it.

## Exact classification behavior changed

Before: `mode` was whatever the Supervisor's LLM call returned, with no
correction possible.

After: if the LLM returns any mode other than `coding`/`debugging`, and
the user's raw goal matches at least one of the listed obvious coding
signals, `mode` is forced to `coding` regardless of what the model picked.
The Supervisor can still freely choose `coding` or `debugging` on its own,
and non-coding goals (essays, plans, study explanations) are completely
unaffected — the guardrail only ever moves classification *toward*
`coding`, never away from it.

## Tests added

- `tests/test_mode_classifier.py` (new) — 12 true-positive coding goals,
  5 false-positive non-coding goals, and a dedicated substring-false-positive
  test (`classic`, `codependent`) — 18 tests total, pure function calls, no
  model involved.
- `tests/test_supervisor.py` (new) — exercises the real
  `SupervisorAgent.run()` with `call_model` monkeypatched to return canned
  text (no real model call): the exact regression case
  (`general`→`coding` override), no-override when the model already says
  `coding`, no-override when the model says `debugging`, no-override for a
  genuine non-coding goal, override even when the model picks `writing`
  for an obviously-coding goal, and confirmation that ordinary parsing
  (refined goal + mode, e.g. `study`) is unaffected when no override is
  needed — 6 tests total.

## Tests run

```
ruff check .                                                → All checks passed!
pytest tests/test_mode_classifier.py tests/test_supervisor.py -v  → 24 passed
pytest tests/ -v                                            → 227 passed
```

## Eval result

Ran `eval_simple_coding_task` directly (not the full suite, since it
involves several slow, real local-model calls unrelated to this fix):

```python
from eval.scenarios import eval_simple_coding_task
result = eval_simple_coding_task()
```

**First attempt: `fail`.** The Supervisor override worked correctly
(`[Supervisor] Overriding mode 'general' -> 'coding'`), code verification
passed, and the Judge scored 100/100 — but the run then failed at the
final Synthesizer step because `qwen2.5-coder:14b` and its fallback
`llama3.2:3b` both timed out. `ollama ps`/`vm_stat` showed both an 11 GB
and a 4 GB model loaded simultaneously with very little free memory
(~295 MB free pages) — a transient local resource/timeout issue, not a
classification regression, and out of this phase's scope (memory/model
scheduling was addressed separately in Phase 6).

**Second attempt (retry, models already warm): `pass`.**

```
NAME: eval_simple_coding_task
STATUS: pass
MESSAGE: code_verification succeeded (1 check(s) run).
```

The full pipeline log confirms the fix end-to-end:
`[Supervisor] Overriding mode 'general' -> 'coding' (deterministic
coding-signal guardrail)`, `Mode: coding`, `CODE EXECUTION PASSED`,
`Judge Score: 100/100 (PASS)`, and a completed Synthesizer step.

## Files changed

- `agents/supervisor.py`
- `prompts/supervisor.txt`
- `orchestrator/mode_classifier.py` (new)
- `tests/test_mode_classifier.py` (new)
- `tests/test_supervisor.py` (new)
- `docs/audits/2026-07-04-phase-12b-maintainer-report.md` (new)

## Remaining risks / TODOs

- The signal-word list deliberately favors recall over precision (per the
  phase's explicit instructions): words like `error`, `bug`, `class`, or
  `api` can appear in non-coding prose (e.g. "human error", "a bug in the
  plan") and could force a false-positive `coding` classification for an
  edge-case non-coding goal. This is a known, accepted tradeoff, not an
  oversight — word-boundary matching only prevents substring false
  positives, not phrase-level ambiguity.
- The eval run that hit a Synthesizer timeout is a reminder that this
  MacBook's memory ceiling makes back-to-back large-model calls
  (`qwen2.5-coder:14b` + fallback `llama3.2:3b`) unreliable under memory
  pressure; this is an existing, separately-tracked resilience/memory
  concern (Phase 6/6b), not something this phase's fix introduces or is
  responsible for resolving.
- The guardrail only ever upgrades ambiguous-or-wrong classifications to
  `coding`; it does not (and per the phase's scope, should not) attempt to
  fix any other mode-confusion pattern (e.g. `planning` vs `study`).

## Release-candidate status

With this fix verified against the real, previously-failing scenario, the
specific blocking finding from the v2.0 final report
(`docs/audits/2026-07-04-v2-maintainer-final-report.md`) is resolved.
Combined with all other Phase 7–12 work already merged and passing, v2.0
is release-candidate ready pending normal PR CI verification for this
branch.

## Commit

```
fix: classify obvious coding goals deterministically
```
