# 05 — Phase 0: Repo Audit and Safety Baseline

## Goal

Understand the current repo before editing anything, and establish a known-good
baseline (clean tree, passing tests, known runtime) that every later phase can
be measured against.

## Why it matters

Every phase after this one claims some kind of improvement — fewer model
calls, faster runtime, cleaner constraint handling. You cannot prove any of
those claims unless you know what "before" looked like. This matters because
without a baseline, "Phase 3 made routing faster" is just an assertion; with a
baseline, it's a number you can compare against `run_summary.json` from a
recorded pre-Phase-3 run.

Phase 0 also exists because this repo has some quirks a fresh reader (or
Claude Code, starting cold) would not otherwise know about: two parallel
pipeline implementations (`run.py` and `orchestrator/graph.py`), extra runner
scripts at the repo root (`run_phase2.py`, `run_phase3.py`) not mentioned
anywhere in the README's repository structure diagram, and a
`docs/research/README.md` that points to filenames that don't actually exist
on disk. Phase 0 is where you confirm all of this before it causes confusion
three phases later.

## Files likely touched

None. Phase 0 is read-only except for creating the feature branch and,
optionally, saving one baseline run's artifacts for later comparison. If you
choose to fix the `docs/research/README.md` filename mismatch noted in
`00-overview.md`, that is the one small, isolated edit this phase may include.

Files to inspect (read-only):

```text
README.md
run.py
run_langgraph.py
run_phase2.py
run_phase3.py
orchestrator/graph.py
orchestrator/state.py
orchestrator/config_loader.py
orchestrator/adapters.py
orchestrator/database.py
orchestrator/logger.py
orchestrator/code_runner.py
config/models.yaml
config/modes.yaml
agents/
tests/
docs/research/README.md
```

## Exact implementation instructions

1. Confirm you're on `main` and the tree is clean, then create the phase
   branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git status --short
```

```bash
git checkout main
git checkout -b phase-0-repo-audit
```

2. Run the existing test suite and lint check to confirm the starting point
   is actually green:

```bash
ruff check .
```

```bash
pytest tests/ -v
```

3. Inspect the config files and note the active profile and model mix (this
   becomes relevant in Phase 6):

```bash
cat config/models.yaml
```

4. Confirm whether `run.py` and `orchestrator/graph.py` are both still in
   use, or whether one has become dead code. Read both entry points
   (`run.py`, `run_langgraph.py`) and compare — do they implement the same
   pipeline logic. If they've drifted apart, note this as a risk for later
   phases rather than silently picking one.

5. If practical (Ollama running, at least the small model pulled), record one
   baseline run's timing and outcome. Use a small model so this doesn't take
   twelve minutes:

```bash
curl --fail http://localhost:11434
```

```bash
ollama list
```

```bash
time python run.py \
  --goal "Write a 100-word explanation of why sleep deprivation hurts productivity." \
  --model-main llama3.2:3b \
  --model-fast llama3.2:3b \
  --max-loops 2 \
  --threshold 65
```

Copy the resulting `runs/<timestamp>/run_summary.json` somewhere you can
refer back to later (for example, note the run's timestamp folder name in
your own notes — do not commit it, since `runs/` is git-ignored on purpose).

6. If you want to fix the `docs/research/README.md` filename mismatch noted
   in `00-overview.md` (it references `2026-07-04-v1-to-v2-architecture-strategy.md`
   and `2026-07-04-cloud-fallback-sonnet-workflow-quality.md`, but the real
   files are the `compass_artifact_wf-...` names), do that now as a single
   small, isolated edit — it's a documentation correction, not a code change,
   and it's the kind of thing worth cleaning up before it causes confusion in
   a later phase.

## Tests to add

None. Phase 0 does not add new test coverage — it confirms existing coverage
passes.

## Commands to run

```bash
git status --short
ruff check .
pytest tests/ -v
```

## Expected output

- `git status --short` shows a clean tree (or only the `docs/research/README.md`
  fix, if you chose to make it).
- `ruff check .` reports no violations.
- `pytest tests/ -v` shows all existing tests passing (`test_judge.py`,
  `test_database.py`, `test_code_runner.py`).
- If you ran a baseline pipeline run, `runs/<timestamp>/run_summary.json`
  exists and shows a `stop_reason`, `final_score`, and `scores` list.

## If it fails

- Ruff or pytest fail on a clean checkout of `main`: stop. This means v1.0.0
  itself has a regression unrelated to this upgrade guide — fix that on its
  own branch first, before starting any phase work.
- Ollama isn't running or the small model isn't pulled: skip the baseline
  timing run rather than forcing it. Note in your own records that no
  baseline was captured, and capture one later once Ollama is available.

## Rollback plan

Phase 0 makes no risky changes. If you made the `docs/research/README.md`
fix and want to undo it:

```bash
git checkout main -- docs/research/README.md
```

To abandon the branch entirely:

```bash
git checkout main
git branch -D phase-0-repo-audit
```

## Commit suggestion

```text
docs: fix research report filenames referenced in docs/research/README.md
```

(Only relevant if you made that one fix. If Phase 0 was purely read-only,
there is nothing to commit — that's fine, move to Phase 1 with an empty diff.)

## Done when

```text
The repo is clean, ruff and pytest both pass on main, you understand whether
run.py and orchestrator/graph.py have diverged, you know your active model
profile, and (if Ollama was available) you have one baseline run_summary.json
to compare later phases against.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 0: repo audit and safety baseline.

Before doing anything, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- README.md
- run.py
- run_langgraph.py
- run_phase2.py
- run_phase3.py
- orchestrator/graph.py
- orchestrator/state.py
- orchestrator/config_loader.py
- orchestrator/adapters.py
- orchestrator/database.py
- orchestrator/logger.py
- orchestrator/code_runner.py
- config/models.yaml
- config/modes.yaml
- docs/research/README.md

Report back:
1. Whether run.py and orchestrator/graph.py implement the same pipeline
   logic, or have diverged, and how.
2. What run_phase2.py and run_phase3.py are for, and whether they are still
   relevant or are leftover scratch scripts.
3. Whether docs/research/README.md references filenames that don't match
   the actual files in docs/research/.
4. The active model profile in config/models.yaml and which roles use
   14B-class models.

Do not modify any file except docs/research/README.md, and only if you find
a real filename mismatch there — if so, fix only that mismatch, nothing else
in the file.

Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote.
Do not commit anything under runs/, logs/, .venv/, or .env.

After inspecting, run:
- ruff check .
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed (if any)
2. Tests run and their results
3. The four findings above
4. A suggested commit message (if a change was made) or "no commit needed"
```
