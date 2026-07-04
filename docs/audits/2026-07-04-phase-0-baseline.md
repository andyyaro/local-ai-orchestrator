# Phase 0 Baseline Audit — 2026-07-04

Source: Phase 0 (`docs/upgrade-guide/05-phase-0-repo-audit.md`) executed on
branch `phase-0-repo-audit`. This is a record of the baseline state — it does
not implement any upgrade phase.

## Branch

```text
phase-0-repo-audit
```

## Commands / checks run

```bash
git status --short
git branch --show-current
ruff check .
pytest tests/ -v
curl --fail http://localhost:11434
ollama list
time python run.py \
  --goal "Write a 100-word explanation of why sleep deprivation hurts productivity." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 2 \
  --threshold 65
```

Plus a read-only inspection of every file listed in
`docs/upgrade-guide/05-phase-0-repo-audit.md`'s "Files to inspect" section.

## Ruff result

```text
All checks passed!
```

## Pytest result

```text
13 passed in 0.79s
```

Breakdown: `tests/test_code_runner.py` (6 passed), `tests/test_database.py`
(3 passed), `tests/test_judge.py` (4 passed).

## Baseline run command

```bash
python run.py \
  --goal "Write a 100-word explanation of why sleep deprivation hurts productivity." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 2 \
  --threshold 65
```

Ollama was confirmed running (`curl --fail http://localhost:11434`) and
`llama3.2:3b` was already pulled (confirmed via `ollama list`, alongside
`qwen2.5:14b`, `qwen2.5-coder:14b`, `phi4:14b`, `gemma3:12b`, `llama3.1:8b`,
and others already present locally).

## Baseline run_summary path

```text
runs/20260704_153742/run_summary.json
```

## Baseline score

```text
final_score: 81/100
passed: true
iterations_run: 1
stop_reason: "passed (score 81 >= threshold 65)"
```

## Baseline runtime

```text
525s (8m45s)
```

Notable: this is a single-model run — `llama3.2:3b` was used for **all seven
roles** (supervisor, planner, builder, critic, fixer, judge, synthesizer),
so there was no model-swap cost at all. Nearly 9 minutes for one loop
iteration on the smallest available model suggests per-call latency/prefill
is a real contributor to overall runtime on this hardware, independent of
the model-swap problem Phase 6 targets. Later phases should not assume
Phase 3 (routing) and Phase 6 (memory discipline) alone will fully resolve
the original 12m49s complaint.

Secondary, non-blocking observation: the Builder's draft (llama3.2:3b) drifted
off-topic mid-essay into an unrelated "Backpropagation Analogy" section, and
the Synthesizer's final output ended with a bare "Polished deliverable." line
rather than substantive polish — small-model output-quality artifacts, not a
repo defect, but a relevant data point for evaluating future model-profile
and prompt changes.

## Repo risks found

1. **`run.py` and `orchestrator/graph.py` have genuinely diverged**, not just
   structurally:
   - `orchestrator/graph.py`'s `node_judge()` never calls code verification
     (`verify_draft_code` / `verification_failed`) or an equivalent of
     `_apply_code_verification_to_verdict()` — the LangGraph pipeline has no
     broken-code hard-fail override at all, unlike `run.py`.
   - `orchestrator/graph.py` has zero structured logging — no
     `orchestrator.logger` calls anywhere, unlike `run.py`'s full
     `run_start` / `agent_start` / `agent_end` / `score` / `stop` event trail.
   - `orchestrator/graph.py`'s `node_synthesizer()` writes `run_summary.json`
     to disk but never calls `save_run()` — LangGraph runs are never
     persisted to SQLite and never appear in `show_history.py`.
   - `orchestrator/graph.py`'s hard-fail stop logic treats every hard fail as
     an immediate stop; it is missing `run.py`'s coding-mode special case
     that lets a `broken_code` fail continue looping until `max_loops` so the
     Fixer can use the execution feedback.
   - `_role_model()` logic is duplicated verbatim between the two files
     rather than shared.
   - Practical implication: any phase that only patches `run.py` (validators,
     resilience, metrics) will silently leave `orchestrator/graph.py` further
     behind unless explicitly mirrored.

2. **`run_phase2.py` and `run_phase3.py` are confirmed superseded milestone
   scripts**, not active code: a 2-agent Builder→Critic checkpoint and a
   4-agent Builder→Critic→Fixer→Judge checkpoint (no loop, no Synthesizer, no
   logging, no database save). Neither is imported elsewhere or covered by
   tests. They appear to be incremental build-guide artifacts left in the
   repo root, not part of the current v1.0.0 production pipeline.

3. **`docs/research/README.md` referenced nonexistent filenames**
   (`2026-07-04-v1-to-v2-architecture-strategy.md`,
   `2026-07-04-cloud-fallback-sonnet-workflow-quality.md`) instead of the real
   `compass_artifact_wf-...` files on disk. Fixed during Phase 0 as the one
   permitted documentation cleanup.

4. **Active profile is `serious`**, and per `config/models.yaml` it currently
   assigns three different 14B-class models across roles (`qwen2.5:14b` for
   builder/fixer/synthesizer, `gemma3:12b` for critic, `phi4:14b` for judge)
   — this is the exact model-swap problem Phase 6 exists to fix; confirmed
   still present and unfixed as of this baseline.

5. `runs/` and `history.db` are correctly git-ignored — prior run
   directories and the history database are untracked and do not appear in
   `git status --short`.

## Files changed

```text
docs/research/README.md
```

Only the two filenames were corrected to match what's actually on disk
(`compass_artifact_wf-f402f792-b685-4b93-a2ec-97ba81ce8d8e_text_markdown.md`
and `compass_artifact_wf-f11fd32d-aa8a-4145-ba84-db3f3fd5d412_text_markdown.md`).
No source code was modified.

## Suggested next phase

**Phase 1 — CI foundation** (`docs/upgrade-guide/06-phase-1-ci-foundation.md`),
per the v1.1 order defined in `docs/upgrade-guide/20-final-roadmap.md`. Do not
start Phase 1 until this baseline audit and its findings have been reviewed.
