from orchestrator.code_runner import (
    extract_python_code,
    run_python_code,
    verification_failed,
    verify_draft_code,
)


def test_extract_python_code_prefers_python_block():
    text = """
```text
not python
```

```python
print("hello")
```
"""

    assert extract_python_code(text) == 'print("hello")'


def test_run_python_code_success():
    result = run_python_code('print("hello from test")')

    assert result.success is True
    assert result.returncode == 0
    assert "hello from test" in result.stdout
    assert "CODE EXECUTION PASSED" in result.as_feedback()


def test_run_python_code_failure():
    result = run_python_code("raise ValueError('boom')")

    assert result.success is False
    assert result.returncode != 0
    assert "ValueError" in result.stderr
    assert "CODE EXECUTION FAILED" in result.as_feedback()
    assert verification_failed(result.as_feedback()) is True


def test_run_python_code_blocks_unsafe_pattern():
    result = run_python_code("import os\nos.system('echo unsafe')")

    assert result.success is False
    assert result.blocked is True
    assert "CODE EXECUTION BLOCKED" in result.as_feedback()
    assert verification_failed(result.as_feedback()) is True


def test_verify_draft_code_with_passing_pytest():
    draft = """
```python
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
```
"""

    feedback = verify_draft_code(draft)

    assert "CODE EXECUTION PASSED" in feedback
    assert "PYTEST VERIFICATION" in feedback
    assert "PYTEST FAILED" not in feedback
    assert verification_failed(feedback) is False


def test_verify_draft_code_without_code_block_fails():
    feedback = verify_draft_code("This answer has no code block.")

    assert "CODE VERIFICATION SKIPPED" in feedback
    assert verification_failed(feedback) is True
