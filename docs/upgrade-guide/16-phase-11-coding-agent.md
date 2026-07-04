# 16 — Phase 11: Claude-Code-Style Coding-Agent Subsystem

## Goal

Build a small, local, public/legal-pattern coding-agent loop — read the repo,
propose a constrained patch, run tests, stop when they pass — inspired by
publicly documented patterns from tools like Claude Code, SWE-agent, Aider,
and OpenHands. This is the most self-referential phase in the whole guide:
you are building a miniature version of the same kind of tool you've been
using to implement Phases 0–10.

## ⚠️ Read this before starting

This phase is categorically riskier than every phase before it, including
cloud fallback and internet access, because **it writes to real files in a
real repository** based on a model's own proposed changes, in a loop that
can run multiple iterations without you reviewing each one individually.
Do not treat this the way you've treated a config flag in earlier phases —
that's the wrong mental model. The mitigations in this phase (target-root
boundary enforcement, minimal-change caps, never auto-committing) are not
optional nice-to-haves; they are the reason this phase is safe to build at
all.

**Never point this subsystem at the Local AI Orchestrator repo itself by
default.** The whole point of a target-root boundary check (step 4 below) is
to stop the coding agent from editing its own codebase while it's supposed
to be working on a separate, disposable practice target. Do all initial
testing against a small scratch repo you create specifically for this
purpose, not against `/Users/andyyaro/Downloads/local-ai-orchestrator`
itself.

Do not copy Claude Code's actual proprietary internals — this phase is
explicitly built from publicly documented patterns (repo mapping, AST/text
search, a todo list, a constrained edit tool, and a test-verify loop), which
is a different thing than reverse-engineering a specific product.

## Files likely touched

```text
coding_agent/                (new top-level package)
coding_agent/repo_map.py      (new — AST + text search over a target repo)
coding_agent/todo_state.py    (new — structured, persisted task tracking)
coding_agent/patch_tool.py    (new — constrained, boundary-checked file writes with diff preview)
coding_agent/test_loop.py     (new — run tests in the target repo, and the read/edit/test loop)
tests/test_coding_agent.py    (new)
```

Files to inspect first (read-only):

```text
orchestrator/code_runner.py
orchestrator/pytest_runner.py
agents/base_agent.py
```

`orchestrator/code_runner.py`'s `BLOCKED_PATTERNS` list (dangerous
constructs like `eval`, `exec`, `os.system`, network calls) already exists
for single-snippet execution — this phase reuses that same list when
scanning a proposed file's *new content* before writing it, rather than
inventing a second, possibly-inconsistent blocklist.

## Exact implementation instructions

1. Create the branch:

```bash
cd /Users/andyyaro/Downloads/local-ai-orchestrator
git checkout main
git checkout -b phase-11-coding-agent
```

2. Before writing any code, create a small, disposable scratch repo to test
   against — never the orchestrator repo itself:

```bash
mkdir -p /tmp/coding-agent-scratch
cd /tmp/coding-agent-scratch
git init
```

   Add one tiny Python file with a deliberately broken function and a
   pytest test that currently fails against it — this becomes your fixture
   for steps 6–8 below.

3. Create `coding_agent/repo_map.py`:

   - `build_repo_map(target_root: Path) -> dict` — walks `target_root`
     (skipping `.git/`, `.venv/`, `node_modules/`, and anything matching
     the target repo's own `.gitignore` if present), and for every `.py`
     file, uses Python's built-in `ast` module to extract top-level function
     and class names with line numbers. This gives the agent a lightweight
     map of "what exists" without reading every file's full contents into
     context.
   - `search_repo(target_root: Path, pattern: str) -> list[Match]` — shells
     out to `ripgrep` (`rg`) via `subprocess` if it's installed, and falls
     back to a plain-Python recursive text search if it isn't. Never
     attempt to install `ripgrep` automatically — if it's missing, use the
     fallback and note it, the same "never auto-install tooling" discipline
     used everywhere else in this guide.

4. Create `coding_agent/patch_tool.py` — the constrained edit tool. This is
   the single most important file in this phase:

   - `propose_change(target_root: Path, relative_path: str, new_content: str) -> PatchPreview`
     — resolves `relative_path` against `target_root`, and **must reject**
     the change (return `allowed=False` with a clear reason) if the
     resolved absolute path is not a descendant of `target_root` (this is
     the defense against path traversal, e.g. a proposed path like
     `"../../etc/hosts"`). If allowed, generate a unified diff (via
     `difflib.unified_diff`) between the current file content (or empty, if
     new) and `new_content`, and return it as a `PatchPreview` without
     writing anything yet.
   - Before marking a change `allowed=True`, scan `new_content` using the
     same `find_blocked_pattern()` logic already in
     `orchestrator/code_runner.py` — reuse that function directly (import
     it) rather than re-implementing the pattern list a second time. A
     proposed file containing a blocked pattern must never be written.
   - `apply_change(preview: PatchPreview) -> None` — actually writes the
     file, and only ever called after `propose_change` returned
     `allowed=True`. Log every applied change (path, diff, timestamp) to a
     per-session change log file so there's always a full audit trail,
     independent of whether the target repo is even under Git.

5. Create `coding_agent/todo_state.py`:

   - `class TodoState`: a simple, persisted (JSON file per session) list of
     steps with `status` in `{"pending", "in_progress", "done"}`. This gives
     both the loop and you, reviewing afterward, visibility into what the
     agent thought it was doing at each point — not just what it actually
     changed.

6. Create `coding_agent/test_loop.py`:

   - `run_repo_tests(target_root: Path, test_path: str | None = None) -> TestResult`
     — runs `pytest` as a subprocess inside `target_root` (with a timeout,
     mirroring `orchestrator/pytest_runner.py`'s existing conventions but
     scoped to a whole target repo rather than one extracted snippet), and
     returns pass/fail plus captured output.
   - `coding_agent_loop(goal: str, target_root: Path, max_iterations: int = 5) -> LoopResult`
     — the read/edit/test loop:
     1. Refuse to proceed at all if `target_root` resolves to this
        project's own repo root, unless an explicit
        `allow_self_repo: bool = False` parameter is passed as `True` —
        make this the loudest, hardest-to-miss check in the whole function.
     2. Build the repo map and run a relevant `search_repo` query based on
        the goal.
     3. Ask a coding-capable local model (reuse the existing agent/model
        plumbing — a `CodingAgentModel` role reusing `BuilderAgent`'s
        pattern is reasonable) to propose one file's full new content for
        one specific, named file.
     4. Call `propose_change()`. Enforce a **minimal-change guardrail**: if
        the diff changes more than a configured line-count threshold, do
        not auto-apply — stop the loop and report the oversized proposed
        change for manual review instead. This is the "minimal-change rule"
        from the master goals, enforced as a real, checked limit rather
        than a suggestion in a prompt.
     5. If under the threshold, `apply_change()`, then `run_repo_tests()`.
     6. If tests pass, stop successfully and report what changed. If tests
        fail, feed the failure output back to the model as context for the
        next iteration, update `TodoState`, and loop again — up to
        `max_iterations`, after which stop and report the remaining
        failure rather than looping forever.
   - Never call `git commit`, `git push`, or any tagging command from
     within this loop. Applying a change to disk is the loop's job;
     deciding whether to commit it is yours.

## Tests to add

Create `tests/test_coding_agent.py`, using `tmp_path` (pytest's built-in
temporary directory fixture) for every test — never the real orchestrator
repo:

- `build_repo_map` correctly extracts function/class names from a small
  fixture Python file written into `tmp_path`.
- `search_repo` finds an expected match in a fixture file, and the
  ripgrep-unavailable fallback path (force it by mocking `subprocess.run` to
  raise `FileNotFoundError`) still returns correct results via the
  pure-Python fallback.
- `propose_change` rejects a path that resolves outside `target_root` (a
  constructed `"../"`-style traversal attempt) with `allowed=False`.
- `propose_change` rejects new content containing a blocked pattern (reuse
  a pattern from `orchestrator/code_runner.py`'s existing list, e.g.
  `os.system(...)`, in the test's proposed content).
- `propose_change` returns a correct unified diff for a legitimate,
  in-bounds change.
- `run_repo_tests` correctly reports failure against a fixture package with
  a deliberately failing test, and success once the fixture is patched to
  fix it.
- `coding_agent_loop` refuses to run at all when `target_root` is the
  orchestrator's own repo root and `allow_self_repo` is not explicitly
  `True`.
- `coding_agent_loop`, run against a small fixture package (a tiny module
  plus one failing test) with a scripted/mocked model response that
  produces the correct fix, stops successfully within the iteration limit.
- `coding_agent_loop` stops at `max_iterations` and reports the remaining
  failure when a mocked model response never produces a passing fix.

## Verification

Run the checks below and confirm they match the expected output that follows.

## Commands to run

```bash
ruff check .
pytest tests/test_coding_agent.py -v
pytest tests/ -v
```

## Expected output

- `tests/test_coding_agent.py` passes, entirely within temporary directories
  — no changes to any file in the orchestrator repo itself as a side effect
  of running the test suite.
- The full `tests/` suite still passes.
- A manual run of `coding_agent_loop` against your `/tmp/coding-agent-scratch`
  fixture from step 2 successfully fixes the deliberately broken function
  and stops once its test passes, producing a diff and a todo log you can
  review afterward.

## If it fails

- `coding_agent_loop` runs against the orchestrator repo despite the
  safety check: stop immediately and treat this as a critical bug in this
  phase, not a minor issue — re-check that the path-resolution comparison
  in step 6.1 uses fully resolved absolute paths (`Path.resolve()`) on both
  sides, since a relative-path or symlink mismatch could let the check pass
  when it shouldn't.
- The minimal-change guardrail never triggers even for a large proposed
  diff: check that the line-count threshold is actually being computed from
  the generated unified diff's added/removed line count, not from the raw
  file size.
- Tests hang during the loop: confirm `run_repo_tests()` has a real
  subprocess timeout, mirroring `orchestrator/pytest_runner.py`'s existing
  pattern — an agent-proposed change could plausibly introduce an infinite
  loop in test code, and the harness must not hang waiting for it.

## Rollback plan

Everything this subsystem writes goes through `apply_change()`'s audit log
and stays as uncommitted working-tree changes in whatever `target_root` you
pointed it at — nothing is ever auto-committed. To undo a bad run's changes
in the target repo:

```bash
cd <target_root>
git status --short
git checkout -- .
```

⚠️ Only run `git checkout -- .` in the *target* repo the coding agent was
pointed at, never in the orchestrator repo, and only after confirming with
`git status --short` that you're discarding the agent's changes and nothing
else you wanted to keep.

To remove this phase from the orchestrator project entirely:

```bash
git log --oneline -10
git revert -m 1 <merge-commit-sha>
```

Or, if not yet merged:

```bash
git checkout main
git branch -D phase-11-coding-agent
```

## Commit suggestion

```text
feat: add sandboxed coding-agent loop (repo map, constrained patch tool, test-verify loop)
```

## Done when

```text
The coding-agent can perform a small repo task, apply a patch, run tests,
and stop when tests pass -- against a disposable scratch target repo, never
the orchestrator's own repo unless allow_self_repo is explicitly set to
True, with every write going through the boundary-checked, blocked-pattern-
scanned patch tool and never auto-committing.
```

## Claude Code phase prompt

```text
You are working in /Users/andyyaro/Downloads/local-ai-orchestrator.

Implement only Phase 11: the coding-agent subsystem.

Before editing, run:
git status --short
git branch --show-current

Then inspect these files (read-only, do not edit yet):
- orchestrator/code_runner.py
- orchestrator/pytest_runner.py
- agents/base_agent.py

This phase builds a subsystem that writes to files in a TARGET repo that is
NOT this orchestrator repo by default. Do not test it against this repo's
own files. If you need a scratch target to test against, create one under
/tmp (for example /tmp/coding-agent-scratch) with a tiny Python file and a
deliberately failing pytest test, and use that as your manual test fixture.

Implement the following:
1. coding_agent/repo_map.py: build_repo_map(target_root) using Python's ast
   module for function/class extraction, and search_repo(target_root,
   pattern) using ripgrep via subprocess with a pure-Python fallback if rg
   is not installed (never install it automatically).
2. coding_agent/patch_tool.py: propose_change(target_root, relative_path,
   new_content) that REJECTS any path resolving outside target_root
   (resolve both sides with Path.resolve() before comparing), reuses
   orchestrator/code_runner.py's find_blocked_pattern() to reject unsafe
   proposed content, and returns a PatchPreview with a difflib-generated
   unified diff. apply_change(preview) writes the file only for an allowed
   preview and logs every applied change with its diff to an audit log file.
3. coding_agent/todo_state.py: a simple persisted TodoState (JSON) tracking
   step status (pending/in_progress/done).
4. coding_agent/test_loop.py: run_repo_tests(target_root, test_path) running
   pytest as a subprocess with a timeout, and coding_agent_loop(goal,
   target_root, max_iterations=5, allow_self_repo=False) implementing the
   read/edit/test loop. This function MUST refuse to run at all if
   target_root resolves to this orchestrator repo's own root and
   allow_self_repo is not explicitly True -- make this check loud and
   unmissable. Enforce a minimal-change line-count threshold: an
   oversized proposed diff must stop the loop for manual review rather than
   auto-applying. Never call git commit, git push, or any tag command from
   within this loop.

Create tests/test_coding_agent.py using pytest's tmp_path fixture for every
test -- never the real orchestrator repo. Cover repo_map extraction, the
ripgrep-fallback path, patch_tool's path-traversal rejection and
blocked-pattern rejection, a correct diff for a legitimate change,
run_repo_tests pass/fail behavior, coding_agent_loop's refusal to run
against the orchestrator's own repo root, a successful fixture-based fix
within the iteration limit (using a mocked model response), and a
max-iterations stop when a mocked response never fixes the fixture.

Do not modify any file outside this scope.
Do not run this subsystem against /Users/andyyaro/Downloads/local-ai-orchestrator
itself at any point during implementation or testing.
Do not enable cloud calls or change the active provider.
Do not run `ollama pull` or download any model.
Do not tag a release or bump a version number.
Do not merge to main, push to a remote, or run any git commit/push from
inside the new coding_agent code, unless explicitly told to in this session
and only for the orchestrator repo's own phase branch.
Do not commit anything under runs/, logs/, .venv/, or .env.

After editing, run:
- ruff check .
- pytest tests/test_coding_agent.py -v
- pytest tests/ -v
- git status --short

Stop after reporting:
1. Files changed
2. Tests run and their results
3. Confirmation that no test or manual check wrote to this orchestrator
   repo's own files
4. Any remaining risks or TODOs
5. A suggested commit message
```
