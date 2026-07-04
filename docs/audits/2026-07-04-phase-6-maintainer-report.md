# Phase 6 Maintainer Report — MacBook Memory Discipline

## Gap being closed

Repo inspection confirmed the problem the guide describes exactly:
`config/models.yaml`'s `serious` profile mixed **three** distinct
14B-class models (`qwen2.5:14b`, `gemma3:12b`, `phi4:14b`) across its seven
roles, and `coding` mixed three more (`qwen2.5-coder:14b`, `gemma3:12b`,
`phi4:14b`). Each is roughly 9GB at Q4_K_M. Two 14B-class models cannot
be co-resident on a 24GB Mac (macOS caps GPU-usable unified memory at
roughly two-thirds of total RAM, ~16GB usable) — every run using either
profile paid real model-swap cost as Ollama repeatedly unloaded and
reloaded models across the pipeline's roles.

## Changes made

1. **`config/models.yaml`** — `serious` and `coding` now each use exactly
   one distinct 14B-class model family across all seven roles (heavy roles
   share it; supervisor/planner/critic share `llama3.1:8b`). Added a new
   `low_memory` profile with zero 14B-class models, for runs that need to
   coexist with other memory pressure. Added a `context_sizes` block
   (`bootstrap`/`fast`: 4096, `serious`/`coding`: 8192, `low_memory`: 2048)
   read via the new `get_num_ctx_for_profile()` getter — larger `num_ctx`
   directly multiplies KV cache memory use, so `low_memory` intentionally
   uses a much smaller window.
2. **`orchestrator/config_loader.py`** — added
   `get_num_ctx_for_profile(profile_name=None) -> int`, reading the new
   `context_sizes` block and falling back to `defaults.num_ctx`. This is a
   passive getter only; it is not yet wired into `agents/base_agent.py` or
   `run.py` (see "Not wired" below — this matches the guide's own
   phase prompt, which explicitly excludes editing `run.py`/agent code in
   this phase).
3. **`docs/model-profiles.md`** (new) — explains each profile's purpose,
   the ~16GB usable memory ceiling math, when to use `low_memory` vs.
   `serious` vs. `coding`, and documents two deliberate deviations from the
   guide's literal example (see below).
4. **`scripts/local_acceptance.sh`** (new, executable, not wired into CI)
   — manual smoke test that checks Ollama is reachable and runs a
   `llama3.2:3b` pipeline call, verifying `run_summary.json` and
   `final_output.txt` exist. Never calls `ollama pull`.
5. **`tests/test_model_config.py`** (new) — real enforcement tests: every
   profile has at most one distinct 14B-class model name; `serious` and
   `coding` each have exactly one; `low_memory` has zero; every profile
   defines all of `orchestrator.config_loader.VALID_ROLES`;
   `get_num_ctx_for_profile("low_memory") < get_num_ctx_for_profile("serious")`;
   and an unlisted profile falls back to `defaults.num_ctx`.
6. **`README.md`** — added `low_memory` to the listed profiles and linked
   `docs/model-profiles.md`.

## Deviations from the guide's literal example (and why)

- **`coding` profile's `synthesizer` role uses `llama3.1:8b`, not
  `qwen2.5:14b`** as the guide's draft example showed. The guide's own
  stated reasoning for that choice ("keep it on the same family as
  serious's heavy model... to avoid a second resident 14B family") doesn't
  hold up: `qwen2.5:14b` and `qwen2.5-coder:14b` are different weight
  files with no shared residency in Ollama, so following the literal
  example would have put **two** distinct 14B-class models in the
  `coding` profile — precisely the problem this phase exists to eliminate,
  and something `tests/test_model_config.py` would then fail on. Assigning
  `synthesizer: "llama3.1:8b"` keeps exactly one 14B-class family resident
  in `coding`, mirroring the pattern already used in `serious`. Documented
  in full in `docs/model-profiles.md`.
- **`mode_overrides` was left unchanged**, with a new comment flagging a
  known limitation: `mode_overrides` applies regardless of `active_profile`,
  so `active_profile: serious` combined with a goal classified
  `mode="coding"` can still produce two resident 14B-class families for
  that one run (builder/fixer switch to `qwen2.5-coder:14b` while judge/
  synthesizer stay on `serious`'s `qwen2.5:14b`). This is a pre-existing
  characteristic of how `get_model_for_role()` layers `mode_overrides`
  over the active profile, not something Phase 6 introduced. The guide's
  explicit instructions and "Files likely touched" list don't mention
  `modes.yaml` or the `mode_overrides` block, and fixing it fully would
  require making profile selection mode-aware — a larger design change
  than "keep each profile internally consistent." Documented as a known
  follow-up in both `config/models.yaml` (inline comment) and
  `docs/model-profiles.md` rather than silently patched or silently
  ignored.
- **`get_num_ctx_for_profile()` is not wired into the runtime pipeline**
  in this phase. The getter exists and is tested, but `agents/base_agent.py`
  and `run.py` still use the hardcoded `num_ctx=4096` default from
  `BaseAgent.__init__` for every agent regardless of active profile. This
  matches the guide's own "Claude Code phase prompt" section, which
  explicitly says: "Do not modify agent code, run.py, or
  orchestrator/graph.py in this phase — this phase only changes
  configuration, documentation, and a manual script." Wiring the getter
  into the actual per-call `num_ctx` is a natural, low-risk follow-up but
  was intentionally left out to respect this phase's stated scope.

## Files changed

- `config/models.yaml`
- `orchestrator/config_loader.py`
- `README.md`
- `docs/model-profiles.md` (new)
- `scripts/local_acceptance.sh` (new, executable)
- `tests/test_model_config.py` (new)

## Tests run

```
ruff check .                       → All checks passed!
pytest tests/test_model_config.py -v  → 6 passed
pytest tests/ -v                   → 92 passed
```

Verified `tests/test_model_config.py` actually enforces the rule (not just
describes it): temporarily stashing the `config/models.yaml` changes and
re-running the suite reproduced 4 failures against the original
three-14B-model profiles, confirming the test would have caught the
original problem and will catch any future regression.

## Smoke test result

`bash scripts/local_acceptance.sh` was run against the real local Ollama
instance (already running, `llama3.2:3b` already pulled — no model
downloads occurred). It completed successfully:

```
Local acceptance check passed: runs/20260704_170935/
```

Both `run_summary.json` and `final_output.txt` were confirmed present in
that run directory. (The pipeline's own Judge/validator hard-failed the
draft on word-count for an unrelated reason — a 316-word draft against a
50-word target — which is expected pipeline behavior, not a smoke-test
failure; the acceptance script only checks that the pipeline runs
end-to-end and produces its expected artifact files, which it did.)

## Remaining risks / follow-ups

- `mode_overrides` can still combine with `active_profile` to produce two
  resident 14B-class families in one run, as documented above. Tracked as
  a known limitation, not fixed in this phase.
- `get_num_ctx_for_profile()` exists but is not yet wired into the actual
  per-call `num_ctx` used by agents — a future phase (or a small, separate
  follow-up commit) should thread it through `run.py`'s agent construction
  the same way Phase 5b threaded `metrics` through.
- Profile changes were not validated against real output-quality
  regression (e.g., via Phase 12's eval suite, not yet built) — only
  memory/config correctness was verified here, per the guide's own
  rollback-plan note to verify quality impact "with Phase 5's metrics and
  Phase 12's eval suite, not by feel."

## v1.1 completion status

Phases 0 through 6 (routing, validators, resilience, metrics, the Phase 5b
metrics-wiring fix, and now memory discipline) are complete and merged.
This closes out the v1.1 phase list as scoped in
`docs/upgrade-guide/20-final-roadmap.md`'s v1.1 section — no further v1.1
phases remain.

## Phase 7 readiness

Yes — nothing in this phase blocks Phase 7 (cloud fallback). The
resilience layer's cloud-backoff branch (built in Phase 4, still
unreachable via Ollama) and the model-profile structure here are both
stable foundations for that work. Phase 7 was not started.

## Commit

```
chore: tune local model profiles for MacBook memory discipline
```
