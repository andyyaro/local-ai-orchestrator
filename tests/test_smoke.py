"""Smoke tests for the initial project scaffold."""

from __future__ import annotations

from pathlib import Path


def test_required_scaffold_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required_paths = [
        root / "run.py",
        root / "requirements.txt",
        root / "config" / "models.yaml",
        root / "config" / "modes.yaml",
        root / "agents" / "supervisor.py",
        root / "prompts" / "supervisor.md",
    ]

    missing = [str(path.relative_to(root)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing scaffold files: {missing}"
