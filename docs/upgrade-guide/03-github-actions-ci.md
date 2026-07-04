# 03 — GitHub Actions CI Foundation (Track A)

## 3.1 What this section covers

This section defines **Track A**: `​.github/workflows/ci.yml`, the GitHub-hosted
automated checker described in `00-overview.md`. This is the *design and
reference* for that workflow. The step-by-step "implement it now" instructions,
with a Claude Code prompt and a done-when checklist, live in Phase 1
(`06-phase-1-ci-foundation.md`, planned). Read this section first so you
understand what Phase 1 is building and why.

## 3.2 Why GitHub Actions, and why now

Right now there is no `.github/` directory in this repo at all — CI does not
exist yet. Every check (`ruff check .`, `pytest`) only runs when you remember
to run it by hand. That's fine for a solo v1.0.0 project, but it stops being
fine the moment Claude Code starts making changes across 13 upgrade phases:
you need something that automatically tells you "this branch is broken" every
single time, without you remembering to ask.

This matters because CI is what makes the staged workflow in `00-overview.md`
actually safe. Without it, a silent regression in Phase 2 could sit unnoticed
until Phase 5, at which point you won't know which phase introduced it.

## 3.3 What Track A can and cannot check

Track A runs on GitHub-hosted Linux runners. Those runners do not have Ollama
installed, do not have your Ollama models pulled, do not have your MacBook's
24GB unified memory profile, and do not have network access to
`localhost:11434`. This means Track A can only ever check code that does not
require a real model call.

**Track A can check:**

- Ruff lint compliance across the whole repo.
- Existing unit tests (`tests/test_judge.py`, `tests/test_database.py`,
  `tests/test_code_runner.py` today, plus every new test file added by later
  phases).
- Config loading (`orchestrator/config_loader.py` parsing
  `config/models.yaml` / `config/modes.yaml` correctly).
- SQLite behavior (`orchestrator/database.py`), since SQLite needs no
  external service.
- Validator logic (Phase 2), router logic (Phase 3), and resilience logic
  (Phase 4), once those modules and their tests exist — all of these are pure
  Python and do not call a real model.
- Mocked adapter behavior — a fake `ModelAdapter` that returns canned text
  instead of calling Ollama, so agent logic can be tested without a live
  model.
- A Streamlit import/smoke check (`streamlit run --headless` or a plain
  `python -c "import app.streamlit_app"`-style check), which catches broken
  imports without needing a browser or real data.

**Track A cannot check:**

- Whether a real Ollama call succeeds.
- Whether a specific model (e.g. `qwen2.5:14b`) produces a good answer.
- Real runtime/latency on your actual hardware.
- Real memory pressure behavior on a 24GB M3 machine.
- Anything about cloud provider behavior, since cloud calls stay disabled
  by default (Phase 7) and are never enabled in CI.

This is why Track B (the self-hosted MacBook runner, `04-self-hosted-macbook-runner.md`)
exists separately — it is the only track that can check the things in the
second list.

## 3.4 The `ci.yml` reference design

The workflow below is the target shape for `.github/workflows/ci.yml`. It is
intentionally minimal at first — it runs whatever tests and lint rules exist
today, and it automatically picks up new test files as later phases add them,
without needing to be edited every time.

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install ruff

      - name: Run Ruff
        run: ruff check .

      - name: Run pytest
        run: pytest tests/ -v

      - name: Streamlit import smoke test
        run: python -c "import app.streamlit_app"
```

Notes on specific choices, so Claude Code (or you) doesn't "helpfully" change
them without understanding why:

- **`python-version: "3.12"`**, not `3.14`. Your local machine runs Python
  3.14.0, but GitHub-hosted runner Python availability lags behind bleeding-edge
  releases, and pinning to a stable, widely-available version keeps CI from
  breaking for reasons that have nothing to do with your code. If you later
  confirm `3.14` is reliably available on `actions/setup-python`, this can be
  bumped in its own small commit — not silently changed as a side effect of
  an unrelated phase.
- **`pip install ruff` is explicit**, because `requirements.txt` does not
  currently list Ruff even though the project uses it (verified: Ruff is not
  in `requirements.txt`, only `black` is listed under dev tools). Do not
  assume Ruff is already installed via `requirements.txt`.
- **`pytest tests/ -v`** runs the whole `tests/` directory rather than naming
  individual files. This means every phase's new test file (validators,
  router, resilience, metrics, cloud policy, etc.) is automatically included
  once it's added — you should not need to edit `ci.yml` again just because
  Phase 2 added `tests/test_validators.py`.
- **`on.push.branches: ["**"]`** runs CI on every branch push, not just
  `main` — this is what gives you a check on each `phase-N-*` branch before
  you ever open a PR.
- There is deliberately no `workflow_dispatch`, no self-hosted runner
  reference, and no model download step in this file. Track A never touches
  Ollama or your Mac.

## 3.5 What Phase 1 will actually do with this

Phase 1 (`06-phase-1-ci-foundation.md`) is the concrete task of creating this
exact file, committing it on a `phase-1-ci-foundation` branch, pushing it, and
confirming in the GitHub Actions tab that it runs and passes. That phase
section will give you the branch commands, the Claude Code prompt, and the
done-when checklist. This section's job was only to explain the design so
that when you read Phase 1, none of it is a surprise.

## 3.6 Safety notes specific to Track A

- CI must never have write access to `main` beyond what a normal PR merge
  requires — do not add a `permissions: contents: write` block or any step
  that pushes commits back to the branch.
- CI must never reference cloud provider secrets. There is nothing in
  `ci.yml` that reads `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or any other
  secret — if a later phase's test needs to simulate a cloud call, it must
  do so with a mock adapter, never a real credential, even in CI's own
  secrets store.
- Do not add automatic tagging, release creation, or `gh release` steps to
  `ci.yml`. Releases stay a manual action you take yourself.

## Verification

Verify:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
ruff check .
```

```bash
pytest tests/ -v
```

```bash
python -c "import app.streamlit_app"
```

Expected result: all three commands succeed locally, exactly mirroring what
`ci.yml` will run on GitHub. If these don't pass locally, `ci.yml` will fail
too — fix locally first.

If it fails: read the specific failing check (Ruff rule name, or pytest test
name) before changing anything. Do not loosen a Ruff rule or delete a test to
make this pass — fix the underlying code.

Done when:

```text
ruff check ., pytest tests/ -v, and the Streamlit import check all pass
locally, matching exactly what the planned ci.yml will run.
```

Commit suggestion (once Phase 1 actually creates the file):

```text
ci: add GitHub Actions workflow for lint and test checks
```
