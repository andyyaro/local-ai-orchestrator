"""
orchestrator/code_runner.py

Extracts Python code from agent output and runs it in a subprocess.
Returns execution results for use in the critique/fix loop.

Safety note: This runs generated code on your local machine.
Only use in coding mode on tasks you trust. This is a developer tool,
not a secure sandbox.
"""

import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


EXECUTION_TIMEOUT = 15

BLOCKED_PATTERNS = [
    r"\bos\.remove\b",
    r"\bshutil\.rmtree\b",
    r"\bshutil\.rmdir\b",
    r"\bos\.rmdir\b",
    r"\bos\.system\b",
    r"\bsubprocess\.(?:run|call|Popen|check_output)\b.*shell\s*=\s*True",
    r"__import__\s*\(\s*['\"]os['\"]\s*\)",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bpip\s+install\b",
    r"\brequests\.",
    r"\burllib\.",
    r"\bsocket\.",
    r"open\s*\(.*['\"]w['\"].*\).*(?:home|Documents|Desktop|Downloads)",
]


class CodeRunResult:
    """Result of a code execution attempt."""

    def __init__(self, success: bool, stdout: str, stderr: str,
                 returncode: int, blocked: bool = False,
                 blocked_reason: str = "", code_found: bool = True):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.blocked = blocked
        self.blocked_reason = blocked_reason
        self.code_found = code_found

    def as_feedback(self) -> str:
        """Format the result as feedback text for the Fixer/Judge."""
        if not self.code_found:
            return (
                "CODE VERIFICATION SKIPPED\n"
                "Reason: No Python code block was found in the draft.\n"
                "For coding mode, include the solution inside a Python code block."
            )

        if self.blocked:
            return (
                "CODE EXECUTION BLOCKED\n"
                f"Reason: {self.blocked_reason}\n"
                "The code was not executed. Remove the flagged pattern and rewrite."
            )

        if self.success:
            output = self.stdout.strip() or "[no stdout]"
            return (
                "CODE EXECUTION PASSED\n"
                "The extracted Python code ran successfully.\n"
                f"STDOUT:\n{output}"
            )

        stderr = self.stderr.strip() or "[no stderr]"
        stdout = self.stdout.strip() or "[no stdout]"
        return (
            "CODE EXECUTION FAILED\n"
            f"Return code: {self.returncode}\n"
            f"STDOUT:\n{stdout}\n\n"
            f"STDERR:\n{stderr}\n"
            "Fix the code so it runs successfully."
        )


def extract_python_code(text: str) -> str:
    """
    Extract the first Python code block from markdown text.
    Falls back to any fenced block if no python-labeled block exists.
    """
    python_blocks = re.findall(
        r"```(?:python|py)\s*\n(.*?)```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if python_blocks:
        return textwrap.dedent(python_blocks[0]).strip()

    generic_blocks = re.findall(r"```\s*\n(.*?)```", text, flags=re.DOTALL)
    if generic_blocks:
        return textwrap.dedent(generic_blocks[0]).strip()

    return ""


def find_blocked_pattern(code: str) -> str:
    """Return the first blocked pattern found, or an empty string."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code, flags=re.IGNORECASE | re.DOTALL):
            return pattern
    return ""


def run_python_code(code: str, timeout: int = EXECUTION_TIMEOUT) -> CodeRunResult:
    """Run Python code in a temporary file and capture the result."""
    if not code.strip():
        return CodeRunResult(
            success=False,
            stdout="",
            stderr="No Python code block found.",
            returncode=1,
            code_found=False,
        )

    blocked = find_blocked_pattern(code)
    if blocked:
        return CodeRunResult(
            success=False,
            stdout="",
            stderr="",
            returncode=1,
            blocked=True,
            blocked_reason=f"Matched blocked pattern: {blocked}",
        )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="orch_code_",
        dir="/tmp",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CodeRunResult(
            success=(result.returncode == 0),
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        return CodeRunResult(
            success=False,
            stdout=exc.stdout or "",
            stderr=f"Execution timed out after {timeout} seconds.",
            returncode=124,
        )
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


def verify_draft_code(draft: str) -> str:
    """
    Extract Python code from a draft, run it, optionally run pytest if tests exist,
    and return feedback text for the pipeline.
    """
    code = extract_python_code(draft)
    result = run_python_code(code)
    feedback = result.as_feedback()

    if result.success:
        try:
            from orchestrator.pytest_runner import has_test_functions, run_pytest_on_code

            if has_test_functions(code):
                pytest_result = run_pytest_on_code(code)
                feedback += "\n\nPYTEST VERIFICATION\n"
                feedback += pytest_result["output"]
                if pytest_result["hard_fail"]:
                    feedback += "\nPYTEST FAILED"
        except Exception as exc:  # pragma: no cover - defensive fallback
            feedback += f"\n\nPYTEST VERIFICATION ERROR\n{exc}"

    return feedback


def verification_failed(feedback: str) -> bool:
    """Return True if verification feedback should force a hard fail."""
    markers = [
        "CODE EXECUTION FAILED",
        "CODE EXECUTION BLOCKED",
        "CODE VERIFICATION SKIPPED",
        "PYTEST FAILED",
        "PYTEST VERIFICATION ERROR",
    ]
    return any(marker in feedback for marker in markers)
