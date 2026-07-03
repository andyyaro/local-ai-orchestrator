"""
orchestrator/pytest_runner.py

Runs pytest on generated Python code and returns structured results.
Used in coding mode when generated code includes pytest-style tests.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path


def has_test_functions(code: str) -> bool:
    """Return True if the code contains pytest-compatible test functions."""
    return bool(re.search(r"^def test_", code, flags=re.MULTILINE))


def run_pytest_on_code(code: str, timeout: int = 30) -> dict:
    """
    Write code to a temp file and run pytest on it.

    Returns:
        dict with keys: passed, num_passed, num_failed, num_errors,
        output, hard_fail.
    """
    if not has_test_functions(code):
        return {
            "passed": None,
            "num_passed": 0,
            "num_failed": 0,
            "num_errors": 0,
            "output": "No test functions found in the generated code.",
            "hard_fail": False,
        }

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_test.py",
        prefix="orchpytest_",
        dir="/tmp",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", tmp_path, "-v", "--tb=short", "--no-header", "-q"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr

        num_passed = len(re.findall(r"\bPASSED\b", output))
        num_failed = len(re.findall(r"\bFAILED\b", output))
        num_errors = len(re.findall(r"\bERROR\b", output))

        return {
            "passed": result.returncode == 0,
            "num_passed": num_passed,
            "num_failed": num_failed,
            "num_errors": num_errors,
            "output": output,
            "hard_fail": result.returncode != 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "passed": False,
            "num_passed": 0,
            "num_failed": 0,
            "num_errors": 1,
            "output": (
                f"Pytest timed out after {timeout} seconds.\n"
                f"STDOUT:\n{exc.stdout or ''}\nSTDERR:\n{exc.stderr or ''}"
            ),
            "hard_fail": True,
        }
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
