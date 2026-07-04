# 02 — How to Use Claude Code for This Upgrade

## 2.1 Starting a session

Open a terminal at the repo root before starting Claude Code — this ensures Claude Code's working directory and tool calls are scoped to the project, not your home folder.

Go to the repo root:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
```

Then start Claude Code from that directory. If you're already inside a Claude Code session reading this guide, you're already positioned correctly — just confirm:

```bash
pwd
```

Expected result: `/Users/andyyaro/Downloads/local-ai-orchestrator`.

## 2.2 What Claude Code should inspect before touching anything

Before implementing any phase, Claude Code should read (not edit) the files relevant to that phase. For most phases, that baseline set includes:

```text
README.md
run.py
orchestrator/config_loader.py
orchestrator/graph.py
config/models.yaml
config/modes.yaml
```

Each phase section later in this guide lists the *additional* files specific to that phase (for example, the validators phase adds `agents/judge.py` and `prompts/judge.txt` to this list).

The point of inspecting first is that this repo has **two parallel pipeline implementations** — the plain `run.py` version and the LangGraph version in `orchestrator/graph.py` — and a change made to one without the other will silently leave the second one behind. Always ask Claude Code to check whether a change needs to be mirrored in both.

## 2.3 Rules to state at the start of every phase session

Paste these constraints at the start of every Claude Code phase prompt, every time. Do not assume a rule stated once persists across sessions:

- Implement only the named phase. Do not start the next phase without being asked.
- Do not modify files outside the phase's stated scope.
- Do not skip or delete failing tests to make the suite pass — fix the underlying code, or stop and report the failure.
- Do not run `git merge`, `git push`, or open a pull request unless explicitly instructed in that session.
- Do not create or push git tags, and do not reference a release version bump.
- Do not change `provider: ollama` to `openai` or `anthropic` in `config/models.yaml`, and do not add real API calls to a cloud provider.
- Do not run `ollama pull` or otherwise trigger a model download — if a phase needs a model that isn't present, report that and ask first.
- Show `git status --short` before making any edits, and again after finishing.

## 2.4 Reusable phase prompt template

Use this template for every phase. Fill in the bracketed parts from the phase's section later in this guide:

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase [N]: [phase name].

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- [file list from the phase section]

Implement the following:
[implementation instructions from the phase section]

Do not modify any file outside this list unless a change is strictly required
to wire the new code in, and if so, explain why before doing it.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main or push to a remote.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest [phase-specific test path] -v
- git status --short

Stop after reporting:
1. Files changed (list them)
2. Tests run and their results
3. Any remaining risks or TODOs
4. A suggested commit message
```

## 2.5 Reviewing Claude Code's changes before committing

Before you tell Claude Code to commit, read the actual diff yourself:

```bash
git diff --stat
```

```bash
git diff
```

Look specifically for: files touched that weren't in the phase's stated scope, any new network call (`requests.`, `urllib.`, `socket.`) outside `orchestrator/adapters.py`'s existing Ollama call, any change to `config/models.yaml`'s `provider:` field, and any new `.env` key.

If it fails: if you see any of these and didn't expect them, ask Claude Code to explain the change before proceeding — don't just accept it because tests passed.

## 2.6 Using Claude Code to fix CI failures

Once Track A (GitHub Actions) exists (Phase 1), a pushed branch may come back with a red check. Ask Claude Code to fix it with a scoped prompt like:

```text
The GitHub Actions run for branch [branch-name] failed. Here is the failure log:
[paste the relevant failing job output]

Fix only the failing test or lint issue. Do not modify unrelated files.
Do not weaken the test to make it pass — fix the underlying code, unless the
test itself is provably wrong, in which case explain why before changing it.
Run the same check locally (ruff check . / pytest [path] -v) before reporting done.
Show git status --short after.
```

## 2.7 What Claude Code should never be asked to do unsupervised

Even with all the guardrails above stated correctly, don't hand Claude Code these actions without being present and reviewing in real time:

- Merging a PR.
- Force-pushing any branch.
- Deleting a branch other than one you just created.
- Editing `.github/workflows/*.yml` triggers in a way that changes what runs on self-hosted runners (the CI/runner chunk explains why this is specifically dangerous).
- Modifying `.gitignore` to remove an existing ignore pattern.

## Verification

Verify:

```bash
pwd
git branch --show-current
git status --short
```

Expected result: you are at the repo root, on the correct phase branch, with a clean or intentionally-scoped working tree before Claude Code starts editing.

If it fails: fix your working directory or branch before handing Claude Code a phase prompt — don't let it start work from the wrong location or the wrong branch.

Done when:

```text
You have a repo-root terminal session, a checked-out phase branch, and a
Claude Code phase prompt ready that includes the scope, forbidden actions,
and required verification commands from this file.
```
