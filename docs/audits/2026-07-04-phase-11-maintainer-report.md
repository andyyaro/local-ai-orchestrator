# Phase 11 Maintainer Report — Claude-Code-Style Coding-Agent Subsystem

## ⚠️ Read this first

This is the highest-risk phase in the entire v2.0 roadmap: a subsystem
that writes to real files in a real repository based on a model's own
proposed changes, in a loop that can run multiple iterations without
per-change human review. Every claim in this report about safety
behavior was independently verified — not just asserted — by actually
running the boundary checks and confirming the orchestrator repo's own
`git status` was unchanged before and after every test run and the
manual real-model verification below.

## Goal

Build a small, local coding-agent loop — read the repo, propose a
constrained patch, run tests, stop when they pass — inspired by publicly
documented patterns from tools like Claude Code, SWE-agent, Aider, and
OpenHands. Not a reverse-engineering of any specific product's internals.

## What was built

1. **`coding_agent/repo_map.py`** — `build_repo_map(target_root)`: walks
   `target_root` (skipping `.git/`, `.venv/`, `venv/`, `node_modules/`,
   `__pycache__/`, `.pytest_cache/`, and anything matching the target
   repo's own top-level `.gitignore` entries), using Python's `ast`
   module to extract top-level function/class names with line numbers
   per `.py` file. Files that fail to parse are silently skipped rather
   than aborting the whole map. `search_repo(target_root, pattern)`:
   shells out to `ripgrep` via `subprocess` if installed, falling back to
   a pure-Python recursive text search otherwise (or if `rg` errors
   unexpectedly) — never attempts to install `ripgrep` automatically.
2. **`coding_agent/patch_tool.py`** — the single most important file in
   this phase. `propose_change(target_root, relative_path, new_content)`
   **never writes anything**; it only resolves the path, rejects
   (`allowed=False`) anything that resolves outside `target_root` (the
   path-traversal defense — verified against a constructed
   `"../../etc/hosts"`-style attempt), rejects anything matching
   `orchestrator.code_runner.find_blocked_pattern()` (reused directly,
   not re-implemented), and otherwise returns a `PatchPreview` with a
   `difflib.unified_diff`. `apply_change(preview, log_path=None)` writes
   to disk **only** for an already-`allowed=True` preview — raises
   `ValueError` otherwise as a hard backstop — and appends a JSON-lines
   audit entry (timestamp, path, diff) if `log_path` is given.
   `diff_line_count(preview)` counts real changed lines (excluding diff
   file-header boilerplate) for the minimal-change guardrail.
3. **`coding_agent/todo_state.py`** — `TodoState`: a simple, JSON-persisted
   ordered list of steps with `status` in `{pending, in_progress, done}`.
4. **`coding_agent/test_loop.py`** — `run_repo_tests(target_root,
   test_path=None, timeout=60)`: runs `pytest` as a subprocess inside
   `target_root` with a real timeout (mirroring
   `orchestrator/pytest_runner.py`'s existing convention — verified
   against a deliberately hanging test, which correctly timed out at
   `returncode=124` rather than hanging the test suite).
   `coding_agent_loop(goal, target_root, max_iterations=5,
   allow_self_repo=False, max_diff_lines=40, propose_fix_fn=None, ...)`:
   the read/edit/test loop. **The self-repo boundary check runs first,
   before anything else** (before building the repo map, before touching
   `TodoState`) — it fully resolves both `target_root` and this
   orchestrator project's own repo root (computed once via
   `Path(__file__).resolve().parent.parent` at import time, and
   `target_root` re-resolved fresh at every call) and refuses with a
   loud, unmissable `RuntimeError` unless `allow_self_repo=True` is
   passed explicitly. The minimal-change guardrail stops the loop for
   manual review (not auto-apply) when a proposed diff exceeds
   `max_diff_lines`. `propose_fix_fn` is injectable — every test in
   `tests/test_coding_agent.py` supplies its own scripted function; the
   default (`_default_propose_fix`, only reachable when no
   `propose_fix_fn` is passed) reuses `BuilderAgent`'s existing plumbing
   to make a real local-model call, but is **never exercised by any
   automated test in this repo**. The loop never calls `git commit`,
   `git push`, or any tagging command anywhere in its code path.

## Safety verification — not just implemented, actually checked

- **Path traversal**: `test_propose_change_rejects_path_traversal_outside_target_root`
  constructs a `"../../etc/hosts"`-style `relative_path` and confirms
  `allowed=False` with a clear reason. Verified the resolved-path
  comparison uses `Path.resolve()` on both sides, as the guide's "If it
  fails" section specifically warns is the common failure mode.
- **Blocked content**: `test_propose_change_rejects_blocked_pattern_content`
  proposes `import os\nos.system('rm -rf /')\n` and confirms rejection,
  reusing `orchestrator.code_runner.find_blocked_pattern()` directly.
- **Self-repo refusal — verified twice, including the symlink/relative-path
  edge case the guide explicitly calls out**: one test passes
  `_ORCHESTRATOR_REPO_ROOT` directly; a second test `monkeypatch.chdir()`s
  into the orchestrator repo root and passes `target_root="."`, confirming
  the relative-path form is caught too (both resolve to the same absolute
  path before comparison, so neither slips through).
- **Minimal-change guardrail**: `test_coding_agent_loop_stops_for_manual_review_on_oversized_diff`
  constructs a ~200-line proposed change against a 2-line file, confirms
  the loop stops with a `"minimal-change"` reason, and confirms the file
  on disk was **never modified** — the oversized change was rejected
  before `apply_change()` ever ran.
- **Timeout**: `test_run_repo_tests_times_out_cleanly_on_hanging_test`
  writes a test that sleeps 30 seconds, calls `run_repo_tests(...,
  timeout=1)`, and confirms it returns cleanly (`returncode=124`) instead
  of hanging.
- **No orchestrator-repo side effects**: `git status --short` on this
  repo was captured before running `tests/test_coding_agent.py`, again
  after the full automated suite, and again after the manual real-model
  verification run below. All three snapshots were identical (only the
  two new files this phase itself added) — confirmed, not assumed.

## Manual real-model verification (per the guide's explicit request)

Created `/tmp/coding-agent-scratch` (a fresh, disposable `git init`
repo, never the orchestrator repo) with a deliberately broken `add()`
function (`return a - b`) and a failing pytest test expecting the
correct sum. Ran `coding_agent_loop()` **with no scripted
`propose_fix_fn`** — exercising the real default path, a genuine
`BuilderAgent` call to the locally running `qwen2.5-coder:14b` model
(already pulled; no download performed) — targeting only
`/tmp/coding-agent-scratch`.

Result: the loop succeeded on the **first iteration** (`success=True,
iterations_run=1, stop_reason="Tests passed."`), correctly rewriting
`calc.py`'s `add()` to `return a + b` (with docstring and comments the
model added on its own), and produced a real unified diff, a
`todo.json` log showing the step progression, and a `changes.jsonl`
audit entry with the timestamp, path, and diff — all inspected directly
and confirmed present and correct. `git status --short` on the
orchestrator repo was unchanged before and after this run.

## Tests added

`tests/test_coding_agent.py` (19 tests), every one using pytest's
`tmp_path` fixture as `target_root`:

- `build_repo_map`: function/class extraction; `.git`/`.venv` skip
  behavior.
- `search_repo`: expected match found; the ripgrep-unavailable fallback
  (forced via mocking `subprocess.run` to raise `FileNotFoundError`)
  still returns correct results.
- `propose_change`: path-traversal rejection, blocked-pattern rejection,
  correct unified diff for a legitimate change, correct
  `diff_line_count`.
- `apply_change`: refuses to write a rejected preview (and confirms the
  file was never created); writes + logs an audit entry for an allowed
  preview.
- `run_repo_tests`: failure against a broken fixture, success once
  fixed, clean timeout on a hanging test.
- `coding_agent_loop`: refuses to run against the orchestrator's own
  repo root (both the direct-path and relative-path/chdir forms);
  succeeds within the iteration limit with a scripted fix; stops at
  `max_iterations` when the scripted fix never passes; stops for manual
  review on an oversized diff (confirming the file was never modified);
  stops when the scripted fix itself is rejected by `propose_change`
  (confirming the file was never modified).

## Tests run

```
ruff check .                        → All checks passed!
pytest tests/test_coding_agent.py -v → 19 passed
pytest tests/ -v                    → 201 passed
```

## Confirmation: no test or manual check wrote to this orchestrator repo's own files

`git status --short` was captured at three points — before running
`tests/test_coding_agent.py`, after the full automated suite, and after
the manual real-model verification run — and was identical each time
(only `coding_agent/` and `tests/test_coding_agent.py`, this phase's own
new files, ever appeared). No test or manual check ever pointed
`target_root` at `/Users/andyyaro/Downloads/local-ai-orchestrator`
without `allow_self_repo=True` (and no test passes that flag at all).

## Files changed

- `coding_agent/__init__.py` (new)
- `coding_agent/repo_map.py` (new)
- `coding_agent/patch_tool.py` (new)
- `coding_agent/todo_state.py` (new)
- `coding_agent/test_loop.py` (new)
- `tests/test_coding_agent.py` (new)
- `docs/audits/2026-07-04-phase-11-maintainer-report.md` (new)

## Remaining risks / TODOs

- `_default_propose_fix()`'s output-parsing (`FILE: <path>` line plus a
  fenced code block) is a simple, single format. A real coding model
  that doesn't follow this exact format will raise a clear `ValueError`
  rather than silently misbehaving, which is the correct failure mode,
  but a more robust parser (or a structured-output request) would be a
  reasonable follow-up before relying on this for real repeated use.
- `coding_agent_loop`'s minimal-change threshold (`max_diff_lines=40`
  default) and `max_iterations=5` default are reasonable starting points,
  not tuned against real-world usage yet.
- This subsystem has no integration with `run.py`'s main pipeline or
  CLI — it's a standalone set of functions, matching the guide's "narrow,
  separate" framing (similar to Phase 10's `run_research.py`). Wiring a
  CLI entry point (e.g. `python -m coding_agent.test_loop --goal ...
  --target-root ...`) would be a reasonable follow-up if this becomes a
  regularly-used tool rather than a library.
- As with every phase in this project, `allow_self_repo=True` exists as
  an explicit override for advanced/intentional use, but should be
  treated as a "you really mean this" flag, not something to pass
  casually — the whole point of this phase's safety design is that it's
  never the default.

## Commit

```
feat: add sandboxed coding-agent loop (repo map, constrained patch tool, test-verify loop)
```
