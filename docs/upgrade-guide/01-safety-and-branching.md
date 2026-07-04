# 01 — Safety Rules and Branch Strategy

## 1.1 Branch naming

Use one feature branch per phase, named after the phase.

Go to the repo root:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
```

Verify the working tree:

```bash
git status --short
```

Expected result: no output (clean working tree). If you see output, stop and decide whether to commit or stash existing changes before continuing — do not start a phase on top of uncommitted work you don't recognize.

Create the branch for whichever phase you're starting:

```bash
git checkout -b phase-0-repo-audit
```

Later phases follow the same pattern: `phase-1-ci-foundation`, `phase-2-validators`, `phase-3-routing`, and so on. This makes `git log --oneline --graph --all` readable later, and makes rollback trivial — you always know exactly which commits belong to which phase.

## 1.2 Never work directly on `main`

`main` is the branch GitHub treats as the source of truth, the branch your existing release (v1.0.0) was tagged from, and the branch you'd deploy or share from. Every phase in this guide happens on its own branch. Nothing gets merged into `main` except through a pull request that you personally review and approve.

Verify you're not on `main` before editing:

```bash
git branch --show-current
```

Expected result: the name of your phase branch (e.g. `phase-2-validators`), not `main`.

## 1.3 What "safe" means for this project specifically

Given the risks called out in the master goals — Claude Code editing files, GitHub Actions running automatically, and an optional self-hosted runner with access to your real Mac — "safe" means:

- No commit lands on `main` without you reading the diff first.
- No GitHub Actions workflow can tag a release or push to `main` on its own.
- No self-hosted runner job runs on a pull request you didn't open yourself.
- No cloud provider call happens unless you explicitly flip a config flag *and* approve the specific call (Phase 7).
- No model gets downloaded without you typing the `ollama pull` command yourself.
- `runs/`, `logs/`, `.venv/`, and `.env` stay out of Git, exactly as they are today.

Verify this hasn't changed:

```bash
cat .gitignore
```

Expected result: `runs/`, `logs/`, `.venv/`, `.env`, and `__pycache__/` (or equivalent patterns) are present.

If it fails: do not proceed with a phase until `.gitignore` is fixed — a missing ignore pattern here is how you'd accidentally commit your local run history or API keys.

## 1.4 Commit discipline

One phase = one or more small, honestly-scoped commits, never a giant "implement everything" commit. Before every commit, run:

```bash
git status --short
```

Read the output line by line. If you see a file you don't recognize touching (e.g. something in `runs/`, `logs/`, or `.venv/`), do not stage it. Only `git add` the specific files the phase says you should be touching.

## 1.5 Rollback strategy, in general

Because each phase lives on its own branch and has its own commits, rolling back a phase you don't like is one of two operations.

**If you haven't merged yet** — delete the branch:

```bash
git checkout main
git branch -D phase-3-routing
```

⚠️ Warning: this permanently discards the branch's commits. Only do this if you're certain you don't want any part of that work. If you're unsure, rename the branch instead so it's preserved but out of your way:

```bash
git branch -m phase-3-routing phase-3-routing-abandoned
```

**If you already merged into `main`** — revert the merge commit rather than resetting history:

```bash
git log --oneline -10
```

```bash
git revert -m 1 <merge-commit-sha>
```

This creates a new commit that undoes the phase's changes without rewriting history other branches might depend on.

⚠️ Warning: never use `git reset --hard` on `main` after a merge — that rewrites shared history.

Each phase section later in this guide repeats this pattern with phase-specific detail (e.g., "if Phase 4's resilience logic causes more failures than it fixes, revert commit X").

## Verification

Verify:

```bash
git status --short
git branch --show-current
cat .gitignore
```

Expected result:

- Working tree is clean before starting a phase.
- Current branch is a `phase-*` branch, not `main`.
- `.gitignore` still excludes `runs/`, `logs/`, `.venv/`, `.env`.

If it fails:

- Uncommitted changes present: stash or commit them before branching.
- On `main`: create and check out a phase branch before editing anything.
- `.gitignore` missing an entry: fix it in its own small commit before starting the phase.

Done when:

```text
The working tree is clean, you are on a dedicated phase branch, and .gitignore
still protects runs/, logs/, .venv/, and .env.
```
