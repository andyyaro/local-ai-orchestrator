# Model Profiles and Memory Discipline

This document explains what each profile in `config/models.yaml` is for,
the memory math behind why the profiles are shaped the way they are, and
when to reach for `low_memory` instead of `serious` or `coding`.

## The memory ceiling this is designed around

This project was built and tested on a MacBook Pro (Apple Silicon M3, 24GB
unified memory). On Apple Silicon, macOS caps the GPU-usable share of
unified memory at roughly two-thirds of total RAM — about **16GB usable**
on a 24GB machine, once the OS and other running apps are accounted for.

A 14B-class model (`qwen2.5:14b`, `qwen2.5-coder:14b`, `phi4:14b`,
`gemma3:12b`) is roughly **9GB** at Q4_K_M quantization. Two of them do not
fit in ~16GB alongside KV cache and the OS's own footprint —
**a 14B model plus a 3B model can co-reside; two 14B-class models never
can.**

Ollama does not fail loudly when this happens — it queues the request and
unloads an idle model to make room. Each 14B cold-load from disk costs
several seconds up to ~30 seconds. A pipeline run that alternates between
several different 14B-class models across its roles (Supervisor, Planner,
Builder, Critic, Fixer, Judge, Synthesizer) pays that swap cost repeatedly,
on top of already-slow decode speed — often the single largest source of
wasted wall-clock time in a run, separate from how many calls the pipeline
makes.

**The rule every profile in this repo follows: at most one distinct
14B-class model family per profile.** If you edit `config/models.yaml` and
introduce a second 14B-class model name into an existing profile,
`tests/test_model_config.py` will fail — that test exists specifically so
this rule can't silently regress, including in a future automated edit.

## The profiles

| Profile      | Heavy roles (builder/fixer/judge)        | Light roles (supervisor/planner/critic) | Synthesizer     | 14B models resident | `num_ctx` |
|--------------|-------------------------------------------|------------------------------------------|-----------------|----------------------|-----------|
| `bootstrap`  | `llama3.2:3b`                              | `llama3.2:3b`                             | `llama3.2:3b`   | 0                     | 4096      |
| `fast`       | `llama3.1:8b`                              | `llama3.2:3b`                             | `llama3.1:8b`   | 0                     | 4096      |
| `serious`    | `qwen2.5:14b`                              | `llama3.1:8b`                             | `qwen2.5:14b`   | 1 (`qwen2.5:14b`)     | 8192      |
| `coding`     | `qwen2.5-coder:14b`                        | `llama3.1:8b`                             | `llama3.1:8b`   | 1 (`qwen2.5-coder:14b`) | 8192    |
| `low_memory` | `llama3.1:8b`                              | `llama3.2:3b`                             | `llama3.1:8b`   | 0                     | 2048      |

- **`bootstrap`** — smallest possible footprint, everything on `llama3.2:3b`.
  Use for a quick end-to-end sanity check that the pipeline itself works,
  not for real output quality.
- **`fast`** — one 8B model for the roles that benefit from more capability
  (builder/fixer/judge/synthesizer), 3B for the roles that don't need it.
  No 14B model at all, so this is cheap to keep resident alongside other
  apps.
- **`serious`** — the default, general-purpose profile. One 14B-class
  model (`qwen2.5:14b`) handles every role that benefits from stronger
  reasoning (builder, fixer, judge, synthesizer); the lighter roles
  (supervisor, planner, critic) share `llama3.1:8b`, which can stay
  resident next to the 14B model without exceeding the ~16GB ceiling.
- **`coding`** — same shape as `serious`, but the heavy roles use
  `qwen2.5-coder:14b` instead. **Synthesizer here uses `llama3.1:8b`, not
  a 14B model at all** — see "Deviation from the original guide draft"
  below for why.
- **`low_memory`** — reach for this when a run needs to coexist with other
  memory pressure on your Mac (another heavy app open, low battery,
  thermal throttling, or you just want the fastest possible turnaround at
  reduced quality). It never loads a 14B-class model and uses a smaller
  `num_ctx` (2048 vs. 4096–8192 elsewhere), since context window size
  directly multiplies KV cache memory use.

## Deviation from the original guide draft

The Phase 6 upgrade-guide draft's example `coding` profile set
`synthesizer: "qwen2.5:14b"` — i.e., reuse the *same* family as the
`serious` profile's heavy model, reasoning that this avoids "introducing a
second resident 14B family." That reasoning doesn't hold up: `qwen2.5:14b`
and `qwen2.5-coder:14b` are different weight files with no shared
residency in Ollama — assigning them to different roles within the same
profile means **two** distinct 14B-class models can be resident in one
`coding` run, which is exactly the problem this phase exists to eliminate,
and which `tests/test_model_config.py` is designed to catch.

This repo's `coding` profile instead assigns `synthesizer: "llama3.1:8b"`.
The Synthesizer's job is prose polish of the final output, not code
generation, so it was never a good fit for `qwen2.5-coder:14b` in the
first place; falling back to the same light 8B model already used for
supervisor/planner/critic keeps exactly one 14B-class family resident in
the `coding` profile, consistent with every other profile in this file.

## Known limitation: `mode_overrides` can still mix families

`config/models.yaml`'s `mode_overrides` block switches `builder`/`fixer`
to `qwen2.5-coder:14b` whenever the Supervisor classifies a goal's mode as
`coding` or `debugging` — **regardless of the active profile.** If
`active_profile: serious` and a goal gets classified as `coding`, that run
will use `qwen2.5-coder:14b` for builder/fixer while judge and synthesizer
stay on `serious`'s `qwen2.5:14b` — two resident 14B-class families for
that one run, even though the `serious` profile passes
`test_model_config.py` in isolation.

This is a pre-existing characteristic of how `mode_overrides` interacts
with profile selection (`orchestrator/config_loader.get_model_for_role()`
checks `mode_overrides` before falling back to the profile), not something
introduced by this phase. Fixing it fully would mean making profile
selection mode-aware, which is a larger design change than "keep each
profile's own model list internally consistent." Tracked here as a known
follow-up rather than silently patched, since it wasn't in Phase 6's
explicit scope. If you hit this in practice (a `coding`-classified goal
under `active_profile: serious`), switch to the `coding` profile directly
for that run, or override roles manually via `--model-main`.

## `num_ctx` per profile

`orchestrator.config_loader.get_num_ctx_for_profile(profile_name=None)`
reads `config/models.yaml`'s `context_sizes` block for the given profile
(defaulting to the active profile), falling back to `defaults.num_ctx` for
any profile not listed there. Use it instead of hardcoding `4096`
anywhere new context-size logic is added.

## Manual smoke test

`scripts/local_acceptance.sh` runs a `bootstrap`-profile pipeline
end-to-end and checks that `run_summary.json` and `final_output.txt` were
produced. It is intentionally not wired into CI — it requires Ollama
running locally with `llama3.2:3b` already pulled, and fails loudly rather
than pulling anything for you:

```bash
bash scripts/local_acceptance.sh
```
