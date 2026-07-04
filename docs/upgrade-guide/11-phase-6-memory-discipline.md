# 11 — Phase 6: MacBook Memory Discipline

## Goal

Keep the system stable on your actual MacBook Pro (M3, 24GB unified memory)
by eliminating unnecessary model-swapping, giving every profile an explicit
memory budget, and never downloading a model automatically.

## Why it matters

Repo inspection confirms the exact problem both research reports flagged:
`config/models.yaml`'s `serious` profile assigns **three different
14B-class models** across roles —

```yaml
serious:
  supervisor: "llama3.1:8b"
  planner: "llama3.1:8b"
  builder: "qwen2.5:14b"
  critic: "gemma3:12b"
  fixer: "qwen2.5:14b"
  judge: "phi4:14b"
  synthesizer: "qwen2.5:14b"
```

— and the `coding` profile does the same with `qwen2.5-coder:14b`,
`gemma3:12b`, and `phi4:14b`. Each of these is roughly 9GB at Q4_K_M
quantization. Two 14B-class models cannot be co-resident on a 24GB Mac:
macOS caps GPU-usable unified memory at roughly two-thirds of total RAM
(~16GB on a 24GB machine), and 2 × 9GB already exceeds that before KV cache
and the OS's own idle footprint are even counted. Ollama's own behavior
confirms this is costly, not free: when a new model needs to load and there
isn't room, Ollama queues the request and unloads an idle model to make
room — and each 14B cold-load from disk costs several seconds up to ~30
seconds. A single `serious`-profile run today can swap between all three
large models multiple times across a multi-loop run, and every swap adds
real, measured wall-clock time on top of already-slow decode speed. **A 14B
model plus a 3B model can co-reside; two 14B-class models never can.** This
is the single largest lever for cutting the 12m49s runtime, separate from
Phase 3's call-count reduction.

This matters because Phase 3 (routing) reduces *how many* calls happen, but
does nothing about *which* models those calls use — a fast-path run that
still alternates between `qwen2.5:14b` and `phi4:14b` for its remaining two
calls still pays a swap cost. Phase 6 fixes the model mix itself.

## Files likely touched

```text
config/models.yaml           (fix model mixing within profiles, add low_memory profile)
docs/model-profiles.md       (new — explains the strategy and memory budget math)
tests/test_model_config.py   (new — enforces "no two distinct 14B models per profile" as a real test)
scripts/local_acceptance.sh  (new — manual small-model smoke test script)
```

Files to inspect first (read-only):

```text
config/models.yaml
orchestrator/config_loader.py
README.md
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-6-memory-discipline
```

2. Fix the model mix within the existing `serious` and `coding` profiles so
   each profile uses **at most one distinct 14B-class model family**,
   assigning that same model to every role that needs "heavy" quality
   (builder, fixer, judge, synthesizer), and a small, fast model to the
   "light" roles (supervisor, planner, critic):

```yaml
profiles:
  bootstrap:
    supervisor: "llama3.2:3b"
    planner: "llama3.2:3b"
    builder: "llama3.2:3b"
    critic: "llama3.2:3b"
    fixer: "llama3.2:3b"
    judge: "llama3.2:3b"
    synthesizer: "llama3.2:3b"

  fast:
    supervisor: "llama3.2:3b"
    planner: "llama3.2:3b"
    builder: "llama3.1:8b"
    critic: "llama3.2:3b"
    fixer: "llama3.1:8b"
    judge: "llama3.1:8b"
    synthesizer: "llama3.1:8b"

  serious:
    supervisor: "llama3.1:8b"
    planner: "llama3.1:8b"
    builder: "qwen2.5:14b"
    critic: "llama3.1:8b"
    fixer: "qwen2.5:14b"
    judge: "qwen2.5:14b"
    synthesizer: "qwen2.5:14b"

  coding:
    supervisor: "llama3.1:8b"
    planner: "llama3.1:8b"
    builder: "qwen2.5-coder:14b"
    critic: "llama3.1:8b"
    fixer: "qwen2.5-coder:14b"
    judge: "qwen2.5-coder:14b"
    synthesizer: "qwen2.5:14b"

  low_memory:
    supervisor: "llama3.2:3b"
    planner: "llama3.2:3b"
    builder: "llama3.1:8b"
    critic: "llama3.2:3b"
    fixer: "llama3.1:8b"
    judge: "llama3.2:3b"
    synthesizer: "llama3.1:8b"
```

   Two deliberate tradeoffs worth stating plainly rather than hiding:

   - **`serious` and `coding` now use the same model for Builder and Judge.**
     This trades some judgment independence (a model scoring its own
     family's output can share blind spots) for a large, measurable memory
     and speed win. If you specifically want an independent Judge model for
     a high-stakes task, override it for that one run with
     `--model-main` pointing Judge elsewhere is not currently possible per-role
     via the CLI (only main/fast bucket overrides exist) — note this as a
     known limitation, not something to silently work around in this phase.
   - **`synthesizer` in the `coding` profile stays on `qwen2.5:14b`, not
     `qwen2.5-coder:14b`.** The Synthesizer's job is prose polish of the
     final output, not further code generation, so reusing the coding
     model there would introduce a second resident 14B family for no
     benefit — keep it on the same family as `serious`'s heavy model, or
     accept the swap cost if you have a specific reason to want
     coder-specific synthesis. Document whichever choice you make.

   - **`low_memory` never loads a 14B-class model at all.** This is the
     profile to reach for if a run needs to coexist with other memory
     pressure on your Mac (another app open, low battery thermal throttling,
     etc.) — it trades output quality for a much smaller and more predictable
     memory footprint.

3. Set explicit `num_ctx` per profile rather than relying only on the single
   global default. Add a `num_ctx` key under each profile (or a parallel
   `context_sizes` block keyed by profile name) — `low_memory` should use a
   smaller context (e.g. `2048`) than `serious`/`coding` (e.g. `4096`–`8192`),
   since context window size directly multiplies KV cache memory use.
   Update `orchestrator/config_loader.py`'s `get_inference_defaults()` (or add
   a new `get_num_ctx_for_profile()`) so this is read per-profile rather than
   only from the single global `defaults.num_ctx`.

4. Write `docs/model-profiles.md` explaining, in plain English: what each
   profile is for, the actual memory math (why two 14B models don't fit,
   citing the ~16GB usable GPU memory ceiling on a 24GB Mac), when to use
   `low_memory` versus `serious` versus `coding`, and an explicit statement
   that no profile should ever be edited to reference two different
   14B-class model families without updating this document's reasoning
   first.

5. Create `scripts/local_acceptance.sh` — a small, manual shell script (not
   run by any CI workflow) that runs a `bootstrap`-profile pipeline smoke
   test end-to-end and checks the expected artifacts exist:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

curl --fail http://localhost:11434

python run.py \
  --goal "Write a 50-word summary of why sleep matters." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 1 \
  --threshold 50

latest_run=$(ls -td runs/*/ | head -1)
test -f "${latest_run}run_summary.json"
test -f "${latest_run}final_output.txt"
echo "Local acceptance check passed: ${latest_run}"
```

   Make it executable:

```bash
chmod +x scripts/local_acceptance.sh
```

   This script does not download any model — it fails loudly via
   `curl --fail` and the subsequent pipeline call if Ollama or the model
   aren't already present, exactly like the Track B workflow in
   `04-self-hosted-macbook-runner.md` does.

6. Create `tests/test_model_config.py` with a real enforcement test, not
   just a descriptive one: parse `config/models.yaml` and assert that **no
   profile references more than one distinct model name matching a
   "14B-class" pattern** (a simple heuristic: model strings containing
   `"14b"` or `"13b"`, case-insensitive). This turns "don't mix multiple 14B
   models in one profile" from a rule you have to remember into a rule CI
   enforces automatically the moment someone (including Claude Code, in a
   future phase) edits `config/models.yaml` carelessly.

## Tests to add

`tests/test_model_config.py` should cover:

- Every profile in `config/models.yaml` references at most one distinct
  14B-class model name across all seven roles.
- Every profile defines all seven required roles (reuse
  `orchestrator.config_loader.VALID_ROLES` rather than hardcoding the list a
  second time).
- The `low_memory` profile specifically contains zero 14B-class model
  references.
- `get_num_ctx_for_profile()` (or equivalent) returns a smaller value for
  `low_memory` than for `serious`.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_model_config.py -v
pytest tests/ -v
bash scripts/local_acceptance.sh
```

## Expected output

- `tests/test_model_config.py` passes, and would fail immediately if a
  future edit reintroduced two different 14B-class models into one profile.
- The full `tests/` suite still passes.
- `scripts/local_acceptance.sh` completes and prints
  `Local acceptance check passed: runs/<timestamp>/`.
- A manual `serious`-profile run's `run_summary.json` (using Phase 5's
  `calls_by_model` field, if that phase has landed) shows only one distinct
  14B-class model name under `calls_by_model`, not three.

## If it fails

- `local_acceptance.sh` fails because Ollama isn't running or
  `llama3.2:3b` isn't pulled: this is expected behavior, not a bug — start
  Ollama and pull the model yourself; the script is intentionally designed
  to fail loudly rather than install anything for you.
- `test_model_config.py` fails on the *existing* `serious`/`coding`
  profiles before you've edited them: that's the test doing its job —
  confirming the original problem — proceed with the profile edits in step 2.
- You genuinely need two different 14B model families for a specific
  experiment: do this as a manual, one-off CLI override
  (`--model-main` / `--model-fast`), not as a permanent profile change, so
  the enforcement test in `config/models.yaml` stays meaningful for the
  default profiles everyone else relies on.

## Rollback plan

If the consolidated single-model-family profiles measurably hurt output
quality more than the speed gain is worth (verify this with Phase 5's
metrics and Phase 12's eval suite, not by feel):

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-6-memory-discipline
```

Reverting this phase specifically means going back to the three-distinct-14B-model
mix — do so deliberately, with the understanding that you're reintroducing
the swap-cost problem this phase exists to fix.

## Commit suggestion

```text
perf: consolidate model profiles to avoid 14B model swapping
```

## Done when

```text
The guide has a clear model strategy that does not overload the 24GB
MacBook: every profile uses at most one distinct 14B-class model family,
a low_memory profile exists with no 14B model at all, num_ctx is set
explicitly per profile, a documented memory-budget rationale exists in
docs/model-profiles.md, and tests/test_model_config.py enforces the
single-large-model-family rule automatically so it can't silently regress.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 6: MacBook memory discipline.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- config/models.yaml
- orchestrator/config_loader.py
- README.md

Implement the following:
1. Edit config/models.yaml so the "serious" and "coding" profiles each use
   at most one distinct 14B-class model family across all seven roles
   (heavy roles share one model; supervisor/planner/critic use a smaller
   fast model). Add a new "low_memory" profile with no 14B-class model at
   all. Add explicit num_ctx settings per profile, smaller for low_memory.
2. Add a get_num_ctx_for_profile() (or equivalent) getter to
   orchestrator/config_loader.py.
3. Create docs/model-profiles.md explaining each profile's purpose, the
   actual memory math for why two 14B models can't co-reside on 24GB, and
   when to use low_memory vs serious vs coding.
4. Create scripts/local_acceptance.sh: a manual bash script that checks
   Ollama is reachable, runs a bootstrap-profile pipeline smoke test with
   llama3.2:3b, and verifies run_summary.json and final_output.txt exist.
   Make it executable. It must never call `ollama pull`.
5. Create tests/test_model_config.py that parses config/models.yaml and
   asserts every profile has at most one distinct 14B-class model name
   (matching "14b" or "13b" case-insensitively) across its seven roles, that
   every profile defines all roles in orchestrator.config_loader.VALID_ROLES,
   and that low_memory has zero 14B-class references.

Do not modify agent code, run.py, or orchestrator/graph.py in this phase —
this phase only changes configuration, documentation, and a manual script.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_model_config.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Any remaining risks or TODOs (including the Builder/Judge shared-model
   tradeoff noted above)
4. A suggested commit message
```
