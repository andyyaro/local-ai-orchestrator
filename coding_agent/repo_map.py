"""
coding_agent/repo_map.py

Read-only repo mapping and text search for Phase 11's coding-agent loop.
Every function here just reads whatever `target_root` the caller passes
-- this module has no opinion about which repo that is; see
coding_agent/test_loop.py's coding_agent_loop() for the actual
self-repo boundary enforcement.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import ast

_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def _load_gitignore_patterns(target_root: Path) -> list[str]:
    gitignore = target_root / ".gitignore"
    if not gitignore.exists():
        return []
    patterns = []
    for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line.rstrip("/"))
    return patterns


def _is_skipped(path: Path, target_root: Path, gitignore_patterns: list[str]) -> bool:
    relative_parts = path.relative_to(target_root).parts
    if any(part in _SKIP_DIRS for part in relative_parts):
        return True
    return any(pattern in relative_parts for pattern in gitignore_patterns)


def build_repo_map(target_root: Path) -> dict:
    """
    Walk `target_root` (skipping .git/, .venv/, node_modules/,
    __pycache__/, .pytest_cache/, and anything matching target_root's own
    top-level .gitignore entries if present), and for every .py file, use
    the ast module to extract top-level function and class names with
    line numbers.

    Returns {relative_path: {"functions": [(name, lineno), ...],
    "classes": [(name, lineno), ...]}} -- a lightweight map of what
    exists, without reading every file's full contents into context.
    Files that fail to parse (syntax errors, undecodable bytes) are
    silently skipped rather than aborting the whole map.
    """
    target_root = Path(target_root).resolve()
    gitignore_patterns = _load_gitignore_patterns(target_root)
    repo_map: dict[str, dict] = {}

    for py_file in target_root.rglob("*.py"):
        if _is_skipped(py_file, target_root, gitignore_patterns):
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="strict")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        functions = []
        classes = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((node.name, node.lineno))
            elif isinstance(node, ast.ClassDef):
                classes.append((node.name, node.lineno))

        relative_path = str(py_file.relative_to(target_root))
        repo_map[relative_path] = {"functions": functions, "classes": classes}

    return repo_map


@dataclass
class Match:
    file: str
    line_number: int
    line_text: str


def _search_repo_fallback(target_root: Path, pattern: str) -> list[Match]:
    """
    Pure-Python recursive text search, used when ripgrep isn't installed
    (or errors unexpectedly). Never installs ripgrep automatically --
    the same "never auto-install tooling" discipline used everywhere
    else in this project.
    """
    gitignore_patterns = _load_gitignore_patterns(target_root)
    matches = []

    for file_path in target_root.rglob("*"):
        if not file_path.is_file() or _is_skipped(file_path, target_root, gitignore_patterns):
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern in line:
                matches.append(Match(
                    file=str(file_path.relative_to(target_root)),
                    line_number=i,
                    line_text=line.strip(),
                ))
    return matches


def search_repo(target_root: Path, pattern: str) -> list[Match]:
    """
    Search `target_root` for `pattern`, preferring ripgrep (`rg`) via
    subprocess if installed, falling back to a pure-Python recursive text
    search otherwise (or if rg errors in an unexpected way). Never
    attempts to install ripgrep.
    """
    target_root = Path(target_root).resolve()

    try:
        result = subprocess.run(
            ["rg", "--line-number", "--no-heading", pattern, str(target_root)],
            capture_output=True, text=True, timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return _search_repo_fallback(target_root, pattern)

    # rg returncode 1 means "ran fine, no matches" -- not an error. Any
    # other non-zero code (rg installed but something else went wrong)
    # falls back too, rather than trusting a possibly-incomplete result.
    if result.returncode not in (0, 1):
        return _search_repo_fallback(target_root, pattern)

    matches = []
    for line in result.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        file_path, line_number, line_text = parts
        try:
            relative_file = str(Path(file_path).resolve().relative_to(target_root))
        except ValueError:
            relative_file = file_path
        try:
            line_number_int = int(line_number)
        except ValueError:
            continue
        matches.append(Match(file=relative_file, line_number=line_number_int, line_text=line_text.strip()))
    return matches
