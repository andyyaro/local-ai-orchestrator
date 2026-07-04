# 06 — Phase 1: CI Foundation

## Goal

Make GitHub Actions check every future change automatically, using the design
established in `03-github-actions-ci.md`.

## Why it matters

Right now there is no `.github/` directory — nothing runs automatically when
you push a branch. Every phase after this one (validators, routing, timeouts,
metrics, and beyond) benefits from having a standing, automatic pass/fail
signal on every push, rather than relying on you remembering to run
`ruff check .` and `pytest tests/ -v` by hand every time. This is also the
first piece of infrastructure Claude Code's future phase work gets checked
against — a red CI run is a fast, unambiguous "something broke," long before
you'd notice it yourself in a manual review.

## Files likely touched

```text
.github/workflows/ci.yml   (new file)
```

Files to inspect first (read-only):

```text
requirements.txt
pyproject.toml
tests/
app/streamlit_app.py
```

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-1-ci-foundation
```

2. Create the `.github/workflows/` directory and add `ci.yml` with exactly
   the content specified in `03-github-actions-ci.md` section 3.4:

```bash
mkdir -p .github/workflows
```

Then create `.github/workflows/ci.yml` with this content:

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

3. Confirm it passes locally before ever pushing, by literally running each
   step from the workflow yourself:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install ruff
ruff check .
pytest tests/ -v
python -c "import app.streamlit_app"
```

4. Push the branch and open a pull request (do not merge it yet):

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow for lint and test checks"
git push -u origin phase-1-ci-foundation
```

5. In GitHub's UI, open the "Actions" tab for the repo and confirm the
   `CI` workflow ran on your push and shows a green check. If you open a
   pull request from this branch, confirm the check shows up on the PR too.

## Tests to add

None new — Phase 1 does not add pipeline logic, it wires up execution of the
tests that already exist (and any future ones).

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/ -v
python -c "import app.streamlit_app"
git status --short
```

## Expected output

- All three checks pass locally.
- After pushing, the GitHub Actions "Actions" tab shows a `CI` run for the
  `phase-1-ci-foundation` branch with a green checkmark.
- `git status --short` shows only `.github/workflows/ci.yml` as new/staged.

## If it fails

- Local `ruff check .` fails: read the specific rule violated, fix the
  underlying code (or, if a rule is genuinely inapplicable to this project,
  add a scoped `per-file-ignore` in `pyproject.toml` with a one-line reason
  — don't disable Ruff globally).
- Local `pytest` fails: this means a currently-broken test predates this
  phase — fix it on this branch before adding CI, since CI would otherwise
  be red from the moment it's created.
- GitHub Actions run fails but the same commands pass locally: this usually
  means a dependency difference between your Mac and the Linux runner (for
  example, a package version pinned differently) — check the Actions log's
  exact error, don't guess.
- The workflow doesn't appear in the Actions tab at all: confirm the file is
  at exactly `.github/workflows/ci.yml` (not `.github/workflow/` or
  `.github/ci.yml`) and that it was actually pushed (`git log --oneline -1`
  on the remote branch).

## Rollback plan

If this workflow needs to be removed or disabled:

```bash
git rm .github/workflows/ci.yml
git commit -m "ci: remove GitHub Actions workflow"
```

If you already merged this into `main` and need to revert it:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

## Commit suggestion

```text
ci: add GitHub Actions workflow for lint and test checks
```

## Done when

```text
GitHub Actions runs Ruff and pytest successfully on push and shows a green
check for the phase-1-ci-foundation branch, with no self-hosted runner and
no cloud provider reference anywhere in ci.yml.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 1: CI foundation.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- requirements.txt
- pyproject.toml
- tests/
- app/streamlit_app.py

Implement the following:
Create .github/workflows/ci.yml with this exact content:

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

Do not modify any file other than creating .github/workflows/ci.yml.
Do not add a self-hosted runner reference to this file.
Do not add any cloud provider secret or API key reference.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote unless explicitly told to in this
session.
Do not commit anything under runs/, logs/, .venv/, or .env.

After creating the file, run:
- ruff check .
- pytest tests/ -v
- python -c "import app.streamlit_app"
- git status --short

Stop after reporting:
1. Files changed (should be exactly .github/workflows/ci.yml)
2. Tests run and their results
3. Any remaining risks or TODOs
4. A suggested commit message
```
