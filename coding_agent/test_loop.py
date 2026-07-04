"""
coding_agent/test_loop.py

The read/edit/test loop for Phase 11's coding-agent subsystem, and the
single hardest boundary check in this project: coding_agent_loop() must
refuse to run at all against this orchestrator's own repo unless
allow_self_repo is explicitly True. Never calls git commit, git push, or
any tagging command -- applying a change to disk is this loop's job;
deciding whether to commit it belongs to whoever calls it.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from coding_agent.patch_tool import apply_change, diff_line_count, propose_change
from coding_agent.repo_map import Match, build_repo_map, search_repo
from coding_agent.todo_state import TodoState

TEST_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_DIFF_LINES = 40

# This orchestrator project's own repo root -- coding_agent_loop refuses
# to point at this (or anything resolving to it) unless allow_self_repo
# is explicitly True. Both sides of the comparison are fully resolved
# (Path.resolve()) at call time in coding_agent_loop(), not just here, so
# a relative-path or symlink mismatch can't slip through.
_ORCHESTRATOR_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TestResult:
    passed: bool
    output: str
    returncode: int


@dataclass
class LoopResult:
    success: bool
    iterations_run: int
    stop_reason: str
    final_diff: str = ""
    todo_state: Optional[TodoState] = None


def run_repo_tests(
    target_root: Path, test_path: str | None = None, timeout: int = TEST_TIMEOUT_SECONDS,
) -> TestResult:
    """
    Run pytest as a subprocess inside `target_root` (optionally scoped to
    `test_path`), with a real timeout mirroring
    orchestrator/pytest_runner.py's existing convention -- an
    agent-proposed change could plausibly introduce an infinite loop in
    test code, and this must not hang waiting for it.
    """
    target_root = Path(target_root).resolve()
    args = [sys.executable, "-m", "pytest"]
    if test_path:
        args.append(test_path)
    args += ["-v", "--tb=short", "--no-header", "-q"]

    try:
        result = subprocess.run(
            args, cwd=target_root, capture_output=True, text=True, timeout=timeout,
        )
        return TestResult(
            passed=(result.returncode == 0),
            output=result.stdout + result.stderr,
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        return TestResult(
            passed=False,
            output=(
                f"Tests timed out after {timeout} seconds.\n"
                f"STDOUT:\n{exc.stdout or ''}\nSTDERR:\n{exc.stderr or ''}"
            ),
            returncode=124,
        )


def _parse_proposed_file(text: str) -> tuple[str, str]:
    file_match = re.search(r"FILE:\s*(\S+)", text)
    code_match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.DOTALL)
    if not file_match or not code_match:
        raise ValueError(
            "Could not parse a 'FILE: <path>' line and a fenced code block "
            "out of the model's response."
        )
    return file_match.group(1).strip(), code_match.group(1)


def _default_propose_fix(
    goal: str, repo_map: dict, search_hits: list[Match], last_test_output: str,
) -> tuple[str, str]:
    """
    Default propose_fix_fn: asks a coding-capable local model (reusing
    BuilderAgent's existing plumbing, per this phase's guide) to propose
    one file's full new content. Never used by tests -- every test in
    tests/test_coding_agent.py injects its own scripted propose_fix_fn
    instead, so this never makes a real model call during the test suite.
    """
    from agents.builder import BuilderAgent
    from orchestrator.config_loader import get_model_for_role

    model = get_model_for_role("builder", "coding")
    agent = BuilderAgent(model=model)

    repo_map_summary = "\n".join(
        f"{path}: functions={[f[0] for f in info['functions']]} "
        f"classes={[c[0] for c in info['classes']]}"
        for path, info in repo_map.items()
    )
    search_summary = "\n".join(
        f"{m.file}:{m.line_number}: {m.line_text}" for m in search_hits[:20]
    )

    context = f"REPO MAP:\n{repo_map_summary}\n\nRELEVANT SEARCH HITS:\n{search_summary}\n\n"
    if last_test_output:
        context += f"PREVIOUS TEST FAILURE OUTPUT:\n{last_test_output}\n\n"
    context += (
        "Respond with EXACTLY one file to change, in this format:\n"
        "FILE: <relative/path/to/file.py>\n"
        "```python\n<the complete new file content>\n```"
    )

    result = agent.run(goal=goal, plan=context, mode="coding")
    return _parse_proposed_file(result)


def coding_agent_loop(
    goal: str,
    target_root: Path,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    allow_self_repo: bool = False,
    max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
    propose_fix_fn: Optional[Callable[[str, dict, list[Match], str], tuple[str, str]]] = None,
    test_path: str | None = None,
    todo_path: Path | None = None,
    change_log_path: Path | None = None,
) -> LoopResult:
    """
    The read/edit/test loop:
      1. REFUSE TO PROCEED AT ALL if target_root resolves to this
         orchestrator project's own repo root, unless allow_self_repo is
         explicitly True. This is the loudest, hardest-to-miss check in
         this function -- it runs before anything else, including
         building the repo map.
      2. Build the repo map and run a relevant search_repo query.
      3. Ask a coding-capable model (propose_fix_fn, defaulting to
         _default_propose_fix's real BuilderAgent call -- injectable so
         tests can supply a scripted response instead) to propose one
         file's full new content.
      4. propose_change(). If the diff exceeds max_diff_lines, stop for
         manual review rather than auto-applying -- the minimal-change
         guardrail, a real checked limit rather than a prompt suggestion.
      5. If under the threshold, apply_change(), then run_repo_tests().
      6. If tests pass, stop successfully. If tests fail, feed the
         failure output back into the next iteration's propose_fix_fn
         call, update TodoState, and loop again up to max_iterations.

    Never calls git commit, git push, or any tagging command.
    """
    resolved_target = Path(target_root).resolve()
    if resolved_target == _ORCHESTRATOR_REPO_ROOT and not allow_self_repo:
        raise RuntimeError(
            "\n"
            "!!! REFUSING TO RUN !!!\n"
            f"target_root resolves to this orchestrator project's own repo "
            f"root ({_ORCHESTRATOR_REPO_ROOT}).\n"
            "The coding-agent subsystem must NEVER edit its own codebase by "
            "default. Point it at a separate, disposable target repo "
            "instead (e.g. /tmp/coding-agent-scratch), or pass "
            "allow_self_repo=True only if you truly intend to run it here.\n"
        )

    todo = TodoState(path=todo_path)
    todo.add_step(f"Understand goal: {goal}", status="in_progress")

    repo_map = build_repo_map(resolved_target)
    first_word = goal.split()[0] if goal.split() else ""
    search_hits = search_repo(resolved_target, first_word) if first_word else []

    propose_fix = propose_fix_fn or _default_propose_fix
    last_test_output = ""
    last_diff = ""

    for iteration in range(1, max_iterations + 1):
        step_index = todo.add_step(f"Iteration {iteration}: propose a fix", status="in_progress")

        relative_path, new_content = propose_fix(goal, repo_map, search_hits, last_test_output)

        preview = propose_change(resolved_target, relative_path, new_content)
        if not preview.allowed:
            todo.update_status(step_index, "done")
            return LoopResult(
                success=False,
                iterations_run=iteration,
                stop_reason=f"Proposed change rejected: {preview.reason}",
                todo_state=todo,
            )

        changed_lines = diff_line_count(preview)
        if changed_lines > max_diff_lines:
            todo.update_status(step_index, "done")
            return LoopResult(
                success=False,
                iterations_run=iteration,
                stop_reason=(
                    f"Proposed change touches {changed_lines} lines, over the "
                    f"{max_diff_lines}-line minimal-change threshold -- "
                    "stopping for manual review instead of auto-applying."
                ),
                final_diff=preview.diff,
                todo_state=todo,
            )

        apply_change(preview, log_path=change_log_path)
        last_diff = preview.diff
        test_result = run_repo_tests(resolved_target, test_path=test_path)

        if test_result.passed:
            todo.update_status(step_index, "done")
            todo.add_step(f"Iteration {iteration}: tests passed", status="done")
            return LoopResult(
                success=True,
                iterations_run=iteration,
                stop_reason="Tests passed.",
                final_diff=last_diff,
                todo_state=todo,
            )

        last_test_output = test_result.output
        todo.update_status(step_index, "done")
        todo.add_step(f"Iteration {iteration}: tests still failing", status="pending")

    return LoopResult(
        success=False,
        iterations_run=max_iterations,
        stop_reason=f"Reached max_iterations ({max_iterations}) without passing tests.",
        final_diff=last_diff,
        todo_state=todo,
    )
