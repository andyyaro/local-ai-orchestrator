"""
tests/test_coding_agent.py

Phase 11: the coding-agent subsystem. Every test uses pytest's tmp_path
fixture as target_root -- NEVER the real orchestrator repo. This is the
highest-risk phase in the project; these tests exist specifically to
prove the safety boundaries (self-repo refusal, path traversal rejection,
blocked-pattern rejection) actually hold, not just that the happy path
works.
"""

import pytest

from coding_agent.patch_tool import apply_change, diff_line_count, propose_change
from coding_agent.repo_map import build_repo_map, search_repo
from coding_agent.test_loop import (
    _ORCHESTRATOR_REPO_ROOT,
    coding_agent_loop,
    run_repo_tests,
)


# ── build_repo_map ─────────────────────────────────────────────────────────────

def test_build_repo_map_extracts_functions_and_classes(tmp_path):
    (tmp_path / "sample.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n\n"
        "class Calculator:\n"
        "    def multiply(self, a, b):\n"
        "        return a * b\n",
        encoding="utf-8",
    )

    repo_map = build_repo_map(tmp_path)

    assert "sample.py" in repo_map
    function_names = [name for name, _ in repo_map["sample.py"]["functions"]]
    class_names = [name for name, _ in repo_map["sample.py"]["classes"]]
    assert "add" in function_names
    assert "Calculator" in class_names


def test_build_repo_map_skips_git_and_venv_directories(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hooks.py").write_text("def hook(): pass\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text("def internal(): pass\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("def real_function(): pass\n", encoding="utf-8")

    repo_map = build_repo_map(tmp_path)

    assert "real.py" in repo_map
    assert not any(".git" in path for path in repo_map)
    assert not any(".venv" in path for path in repo_map)


# ── search_repo ────────────────────────────────────────────────────────────────

def test_search_repo_finds_expected_match(tmp_path):
    (tmp_path / "module.py").write_text(
        "def broken_function():\n    return None  # TODO fix this\n", encoding="utf-8",
    )

    matches = search_repo(tmp_path, "TODO fix this")

    assert any("module.py" in m.file for m in matches)


def test_search_repo_falls_back_to_pure_python_when_ripgrep_missing(tmp_path, monkeypatch):
    (tmp_path / "module.py").write_text(
        "def broken_function():\n    return None  # TODO fix this\n", encoding="utf-8",
    )

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("rg not found")

    monkeypatch.setattr("coding_agent.repo_map.subprocess.run", _raise_file_not_found)

    matches = search_repo(tmp_path, "TODO fix this")

    assert any("module.py" in m.file for m in matches)


# ── propose_change (patch_tool) ─────────────────────────────────────────────────

def test_propose_change_rejects_path_traversal_outside_target_root(tmp_path):
    preview = propose_change(tmp_path, "../../etc/hosts", "malicious content")

    assert preview.allowed is False
    assert "traversal" in preview.reason.lower() or "not inside" in preview.reason.lower()


def test_propose_change_rejects_blocked_pattern_content(tmp_path):
    preview = propose_change(tmp_path, "unsafe.py", "import os\nos.system('rm -rf /')\n")

    assert preview.allowed is False
    assert "blocked pattern" in preview.reason.lower()


def test_propose_change_returns_correct_diff_for_legitimate_change(tmp_path):
    target_file = tmp_path / "calc.py"
    target_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    preview = propose_change(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")

    assert preview.allowed is True
    assert "-    return a - b" in preview.diff
    assert "+    return a + b" in preview.diff


def test_diff_line_count_counts_only_changed_lines(tmp_path):
    target_file = tmp_path / "calc.py"
    target_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    preview = propose_change(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")

    # One line removed, one line added.
    assert diff_line_count(preview) == 2


def test_apply_change_refuses_to_write_a_rejected_preview(tmp_path):
    preview = propose_change(tmp_path, "unsafe.py", "import os\nos.system('boom')\n")

    with pytest.raises(ValueError):
        apply_change(preview)

    assert not (tmp_path / "unsafe.py").exists()


def test_apply_change_writes_file_and_logs_audit_entry(tmp_path):
    preview = propose_change(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")
    log_path = tmp_path / "audit_log.jsonl"

    apply_change(preview, log_path=log_path)

    assert (tmp_path / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"
    assert log_path.exists()
    assert "calc.py" in log_path.read_text(encoding="utf-8")


# ── run_repo_tests ─────────────────────────────────────────────────────────────

def _write_fixture_package(root, add_body: str):
    (root / "calc.py").write_text(f"def add(a, b):\n    {add_body}\n", encoding="utf-8")
    (root / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )


def test_run_repo_tests_reports_failure_against_broken_fixture(tmp_path):
    _write_fixture_package(tmp_path, "return a - b")

    result = run_repo_tests(tmp_path)

    assert result.passed is False
    assert "FAILED" in result.output or result.returncode != 0


def test_run_repo_tests_reports_success_once_fixture_is_fixed(tmp_path):
    _write_fixture_package(tmp_path, "return a + b")

    result = run_repo_tests(tmp_path)

    assert result.passed is True


def test_run_repo_tests_times_out_cleanly_on_hanging_test(tmp_path):
    (tmp_path / "test_hangs.py").write_text(
        "import time\ndef test_hangs():\n    time.sleep(30)\n", encoding="utf-8",
    )

    result = run_repo_tests(tmp_path, timeout=1)

    assert result.passed is False
    assert result.returncode == 124


# ── coding_agent_loop: the self-repo boundary check ────────────────────────────

def test_coding_agent_loop_refuses_to_run_against_orchestrator_repo_root():
    with pytest.raises(RuntimeError, match="REFUSING TO RUN"):
        coding_agent_loop(
            goal="do anything",
            target_root=_ORCHESTRATOR_REPO_ROOT,
            propose_fix_fn=lambda *a: ("x.py", "print('should never run')"),
        )


def test_coding_agent_loop_refuses_even_via_relative_path_to_orchestrator_repo(monkeypatch):
    """The boundary check must compare fully resolved paths -- a
    relative-path or symlink trick must not slip past it."""
    monkeypatch.chdir(_ORCHESTRATOR_REPO_ROOT)
    with pytest.raises(RuntimeError, match="REFUSING TO RUN"):
        coding_agent_loop(
            goal="do anything",
            target_root=".",
            propose_fix_fn=lambda *a: ("x.py", "print('should never run')"),
        )


# ── coding_agent_loop: scripted propose_fix_fn (never a real model call) ──────

def test_coding_agent_loop_succeeds_within_iteration_limit_with_scripted_fix(tmp_path):
    _write_fixture_package(tmp_path, "return a - b")  # starts broken

    def scripted_fix(goal, repo_map, search_hits, last_test_output):
        return "calc.py", "def add(a, b):\n    return a + b\n"

    result = coding_agent_loop(
        goal="fix add",
        target_root=tmp_path,
        max_iterations=3,
        propose_fix_fn=scripted_fix,
        todo_path=tmp_path / "todo.json",
        change_log_path=tmp_path / "changes.jsonl",
    )

    assert result.success is True
    assert result.iterations_run == 1
    assert (tmp_path / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"
    assert (tmp_path / "todo.json").exists()
    assert (tmp_path / "changes.jsonl").exists()


def test_coding_agent_loop_stops_at_max_iterations_when_fix_never_passes(tmp_path):
    _write_fixture_package(tmp_path, "return a - b")  # starts broken, never fixed

    def scripted_never_fixes(goal, repo_map, search_hits, last_test_output):
        # Always "fixes" it wrong, still broken -- but a legitimate,
        # small, in-bounds change each time so it never trips the
        # minimal-change guardrail either.
        return "calc.py", "def add(a, b):\n    return a - b  # still broken\n"

    result = coding_agent_loop(
        goal="fix add",
        target_root=tmp_path,
        max_iterations=3,
        propose_fix_fn=scripted_never_fixes,
    )

    assert result.success is False
    assert result.iterations_run == 3
    assert "max_iterations" in result.stop_reason


def test_coding_agent_loop_stops_for_manual_review_on_oversized_diff(tmp_path):
    _write_fixture_package(tmp_path, "return a - b")

    huge_content = "def add(a, b):\n" + "\n".join(f"    x{i} = {i}" for i in range(200)) + "\n    return a + b\n"

    def scripted_huge_fix(goal, repo_map, search_hits, last_test_output):
        return "calc.py", huge_content

    result = coding_agent_loop(
        goal="fix add",
        target_root=tmp_path,
        max_iterations=3,
        max_diff_lines=10,
        propose_fix_fn=scripted_huge_fix,
    )

    assert result.success is False
    assert "minimal-change" in result.stop_reason
    # The oversized change must never have been applied.
    assert (tmp_path / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"


def test_coding_agent_loop_stops_when_propose_fix_returns_rejected_change(tmp_path):
    _write_fixture_package(tmp_path, "return a - b")

    def scripted_unsafe_fix(goal, repo_map, search_hits, last_test_output):
        return "calc.py", "import os\nos.system('rm -rf /')\n"

    result = coding_agent_loop(
        goal="fix add",
        target_root=tmp_path,
        max_iterations=3,
        propose_fix_fn=scripted_unsafe_fix,
    )

    assert result.success is False
    assert "rejected" in result.stop_reason.lower()
    assert (tmp_path / "calc.py").read_text(encoding="utf-8") == "def add(a, b):\n    return a - b\n"
