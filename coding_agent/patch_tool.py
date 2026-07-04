"""
coding_agent/patch_tool.py

The constrained edit tool for Phase 11's coding-agent loop -- the single
most important file in this phase. propose_change() can only ever build
a diff preview; it never writes anything. apply_change() writes to disk
only for a preview that was already marked allowed=True, and logs every
applied change to an audit trail.
"""

import difflib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from orchestrator.code_runner import find_blocked_pattern


@dataclass
class PatchPreview:
    target_root: Path
    relative_path: str
    resolved_path: Path
    old_content: str
    new_content: str
    diff: str
    allowed: bool
    reason: str = ""


def propose_change(target_root: Path, relative_path: str, new_content: str) -> PatchPreview:
    """
    Resolve `relative_path` against `target_root` and propose writing
    `new_content` there. Never writes anything -- only builds a preview
    for apply_change() to act on later.

    Returns allowed=False with a clear `reason` if:
      - the resolved absolute path is not `target_root` itself or a
        descendant of it (the defense against path traversal, e.g. a
        proposed relative_path like "../../etc/hosts"), or
      - `new_content` matches a pattern in
        orchestrator.code_runner.find_blocked_pattern() -- the same
        blocklist already used for single-snippet execution, reused
        directly rather than re-implemented a second time.
    """
    target_root = Path(target_root).resolve()
    resolved_path = (target_root / relative_path).resolve()

    if resolved_path != target_root and target_root not in resolved_path.parents:
        return PatchPreview(
            target_root=target_root,
            relative_path=relative_path,
            resolved_path=resolved_path,
            old_content="",
            new_content=new_content,
            diff="",
            allowed=False,
            reason=(
                f"Resolved path {resolved_path} is not inside target_root "
                f"{target_root} -- refusing (path traversal guard)."
            ),
        )

    old_content = resolved_path.read_text(encoding="utf-8") if resolved_path.exists() else ""

    blocked = find_blocked_pattern(new_content)
    if blocked:
        return PatchPreview(
            target_root=target_root,
            relative_path=relative_path,
            resolved_path=resolved_path,
            old_content=old_content,
            new_content=new_content,
            diff="",
            allowed=False,
            reason=f"Proposed content matched a blocked pattern: {blocked}",
        )

    diff = "".join(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{relative_path}",
        tofile=f"b/{relative_path}",
    ))

    return PatchPreview(
        target_root=target_root,
        relative_path=relative_path,
        resolved_path=resolved_path,
        old_content=old_content,
        new_content=new_content,
        diff=diff,
        allowed=True,
    )


def diff_line_count(preview: PatchPreview) -> int:
    """
    Count added+removed lines in a preview's unified diff -- used by
    coding_agent/test_loop.py's minimal-change guardrail. Counts only
    lines starting with "+" or "-" that aren't the "+++"/"---" file
    headers, so the count reflects real changed lines, not diff
    boilerplate.
    """
    count = 0
    for line in preview.diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def apply_change(preview: PatchPreview, log_path: Path | None = None) -> None:
    """
    Write `preview.new_content` to `preview.resolved_path`. Only ever
    call this after propose_change() returned allowed=True -- raises
    ValueError otherwise, as a hard backstop against applying a rejected
    preview by mistake.

    If `log_path` is given, appends one JSON-lines entry (timestamp,
    relative_path, diff) to it -- a full audit trail of every applied
    change, independent of whether target_root is even under Git.
    """
    if not preview.allowed:
        raise ValueError(
            f"Refusing to apply a rejected PatchPreview for "
            f"'{preview.relative_path}': {preview.reason}"
        )

    preview.resolved_path.parent.mkdir(parents=True, exist_ok=True)
    preview.resolved_path.write_text(preview.new_content, encoding="utf-8")

    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "relative_path": preview.relative_path,
            "diff": preview.diff,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
