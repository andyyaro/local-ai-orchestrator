# 19 — Rollback Guide

This page consolidates the rollback patterns scattered across every phase
file into one reference. The general rules live in
`01-safety-and-branching.md` section 1.5 — this page adds the
phase-specific nuances that are safer or faster than a full revert.

## The general pattern

Every phase lives on its own branch (`phase-N-name`) with its own commit(s).
This means rollback is almost always one of two operations:

**Not yet merged — delete or rename the branch:**

```bash
git checkout main
git branch -D phase-N-name
```

⚠️ Permanently discards the branch. If unsure, rename instead of deleting:

```bash
git branch -m phase-N-name phase-N-name-abandoned
```

**Already merged — revert the merge commit:**

```bash
git log --oneline -10
```

```bash
git revert -m 1 <merge-commit-sha>
```

⚠️ Never `git reset --hard` on `main` after a merge — that rewrites shared
history other branches or clones may depend on.

## Faster-than-a-full-revert options, by phase

Several phases have a config flag or narrower change that's faster and
safer to flip than reverting a whole merge — use these when the phase's
*infrastructure* is fine but its *default behavior* isn't what you want
right now.

**Phase 3 (routing):** don't revert — set `--path deep` as your default
invocation instead, which makes every run behave like the pre-Phase-3
pipeline while leaving the routing code in place for further tuning.

**Phase 4 (resilience):** set `resilience.max_local_retries: 0` in
`config/models.yaml` to disable the retry-once behavior while keeping typed
exceptions and clean failure handling.

**Phase 6 (memory discipline):** if the consolidated single-model-family
profiles hurt output quality more than the speed gain is worth, this is a
real regression to revert properly (via `git revert`), not just a flag flip
— verify the tradeoff with Phase 5's metrics and Phase 12's eval suite
first, don't decide from a hunch.

**Phase 7 (cloud fallback):** the immediate, zero-risk rollback is simply
confirming `cloud.enabled: false` and never passing `--allow-cloud` — the
scaffolding can sit unused indefinitely.

**Phase 9 (retrieval):** set `memory.retrieval_enabled: false` — no code
change required.

**Phase 10 (deep research):** internet access requires both
`research.internet_enabled: true` and `--enable-research`; unset either to
disable immediately.

**Phase 11 (coding agent):** nothing to disable at the config level — this
subsystem only ever acts on an explicitly-passed `target_root`, and refuses
to run against the orchestrator's own repo unless `allow_self_repo=True`. If
a run against some other target repo went wrong, roll back *that* repo, not
this one:

```bash
cd <target_root>
git status --short
git checkout -- .
```

## If you're not sure which phase caused a problem

```bash
git log --oneline --graph --all
```

Because each phase is its own commit (or small set of commits) on its own
branch, you can check out `main` at different points and re-run the Phase
12 eval suite (`17-phase-12-eval-suite-checklist.md`) to bisect which
phase's merge introduced the regression, rather than guessing.

## What "safe" rollback does not mean

Rolling back a phase does not mean deleting its test file if a test is
merely inconvenient, or commenting out a check that's "probably fine." If a
phase's tests or eval scenarios are failing, that's a signal to fix the
underlying code or genuinely revert the whole phase — not to quietly weaken
the thing that caught the problem.
